"use client";

import { Contract, formatUnits, verifyTypedData } from "ethers";
import streamPayment from "../public/abi/StreamPayment.json";
import erc20 from "../public/abi/ERC20.json";
import {
  loadSettings,
  providerEndpointUrl,
  type AdsConfig,
  type ProviderAd,
  type VMResources,
} from "./api";
import { getRequestorRuntimeConfig } from "./runtimeConfig";
import { getPaymentsSigner, getWalletName } from "./walletClient";
import { walletDebug, walletWarn } from "./walletDebug";

const ZERO_ADDRESS = "0x0000000000000000000000000000000000000000";

export type OpenPaymentStreamOptions = {
  provider: Pick<ProviderAd, "provider_id" | "pricing" | "endpoint_url">;
  resources: VMResources;
  durationSeconds: number;
  ads: AdsConfig;
  account?: string | null;
  vmName?: string;
  image?: string | null;
  purpose?: "new" | "replacement";
  ensurePaymentsNetwork: () => Promise<void>;
  onPhase?: (phase: string) => void;
};

export type OpenedPaymentStream = {
  id: string;
  contractAddress: string;
  image?: string | null;
  payment: {
    stream_id: number;
    lease_id: string;
    terms_hash: string;
    rate_per_second_wei: string;
    duration_seconds: number;
  };
};

export async function openPaymentStream({
  provider,
  resources,
  durationSeconds,
  ads,
  account,
  vmName = "web-rental",
  image,
  purpose = "new",
  ensurePaymentsNetwork,
  onPhase,
}: OpenPaymentStreamOptions): Promise<OpenedPaymentStream> {
  const walletName = getWalletName();
  onPhase?.(
    `Waiting for your approval in ${walletName} to confirm the payment network`,
  );

  onPhase?.("Loading provider lease quote");
  walletDebug("payment-stream:signer:start", {
    providerId: provider.provider_id,
    durationSeconds,
    resources,
  });
  const signer = await getPaymentsSigner({ account, ensurePaymentsNetwork });
  const owner = await signer.getAddress();
  const providerUrl = providerEndpointUrl(provider as ProviderAd);
  const quotedImage = image?.trim() || null;
  walletDebug("payment-stream:quote:start", {
    providerId: provider.provider_id,
    providerUrl,
    requestor: owner,
  });
  const quote = await createLeaseQuote(providerUrl, {
    vm_name: vmName,
    ...(quotedImage ? { image: quotedImage } : {}),
    cpu: resources.cpu,
    memory: resources.memory,
    storage: resources.storage,
    duration_seconds: durationSeconds,
    requestor_address: owner,
  });
  walletDebug("payment-stream:quote:done", {
    providerId: provider.provider_id,
    hasContractAddress: Boolean(quote.contract_address),
    hasGlmTokenAddress: Boolean(quote.glm_token_address),
    hasProviderAddress: Boolean(quote.provider_address),
    hasSignature: Boolean(quote.signature),
    ratePerSecondWei: quote.rate_per_second_wei,
    minDepositWei: quote.min_deposit_wei,
  });
  const cfg = loadSettings();
  const runtimeConfig = getRequestorRuntimeConfig();
  const spAddr = (
    quote.contract_address ||
    cfg.stream_payment_address ||
    runtimeConfig.streamPaymentAddress ||
    ""
  ).trim();
  if (!spAddr) {
    throw new Error(
      "StreamPayment address missing (set in Settings or provided by provider)",
    );
  }

  const token = [
    quote.glm_token_address,
    cfg.glm_token_address,
    runtimeConfig.glmTokenAddress,
  ]
    .map((value) => String(value || "").trim())
    .find((value) => value && value.toLowerCase() !== ZERO_ADDRESS);
  if (!token) {
    throw new Error(
      "GLM token address missing (set in Settings or provided by provider)",
    );
  }

  const glm = new Contract(token, (erc20 as any).abi, signer);
  const ratePerSecondWei = BigInt(quote.rate_per_second_wei);
  const depositWei = BigInt(quote.min_deposit_wei);

  onPhase?.("Checking GLM balance");
  const balance = await glm.balanceOf(owner);
  walletDebug("payment-stream:balance:done", {
    token,
    owner,
    hasEnoughBalance: balance >= depositWei,
    balance: String(balance),
    depositWei: String(depositWei),
  });
  if (balance < depositWei) {
    const symbol = await readTokenSymbol(glm);
    const decimals = await readTokenDecimals(glm);
    throw new Error(
      `Insufficient ${symbol} balance for this payment stream. Required ${formatTokenAmount(
        depositWei,
        decimals,
      )} ${symbol}; available ${formatTokenAmount(balance, decimals)} ${symbol}.`,
    );
  }

  onPhase?.("Checking GLM allowance");
  walletDebug("payment-stream:allowance:start", {
    token,
    streamPayment: spAddr,
    owner,
  });
  const allowance = await glm.allowance(owner, spAddr);
  walletDebug("payment-stream:allowance:done", {
    hasEnoughAllowance: allowance >= depositWei,
    allowance: String(allowance),
    depositWei: String(depositWei),
  });
  if (allowance < depositWei) {
    onPhase?.(
      `Waiting for your approval in ${walletName} to approve GLM spending`,
    );
    walletDebug("payment-stream:approve:start", {
      token,
      streamPayment: spAddr,
      depositWei: String(depositWei),
    });
    const approveTx = await glm.approve(spAddr, depositWei);
    onPhase?.("Waiting for GLM approval confirmation on the blockchain");
    await approveTx.wait();
    walletDebug("payment-stream:approve:done", { txHash: approveTx.hash });
  }

  const contract = new Contract(spAddr, (streamPayment as any).abi, signer);
  const createArgs = [
    quote.provider_address,
    depositWei,
    ratePerSecondWei,
    quote.lease_id,
    quote.terms_hash,
    BigInt(quote.quote_expires_at),
    quote.signature,
  ] as const;
  verifyProviderQuoteSignature({
    quote,
    streamPaymentAddress: spAddr,
    depositWei,
    ratePerSecondWei,
  });
  onPhase?.(
    `Waiting for your approval in ${walletName} to create ${
      purpose === "replacement" ? "the replacement" : "the payment"
    } stream`,
  );
  walletDebug("payment-stream:create:start", {
    streamPayment: spAddr,
    providerAddress: quote.provider_address,
    depositWei: String(depositWei),
    ratePerSecondWei: String(ratePerSecondWei),
  });
  await logCreateStreamDiagnostics({
    signer,
    contract,
    streamPaymentAddress: spAddr,
    tokenAddress: token,
    owner,
    quote,
    depositWei,
    ratePerSecondWei,
    durationSeconds,
    resources,
    vmName,
    image: quotedImage,
    purpose,
    createArgs,
  });
  const populatedTx = await contract.createStream.populateTransaction(
    ...createArgs,
    { gasLimit: 350000n },
  );
  const txData = String(populatedTx.data || "");
  walletDebug("payment-stream:create:tx-populated", {
    to: populatedTx.to,
    dataLength: txData.length,
    selector: txData.slice(0, 10),
    hasValue: populatedTx.value != null && populatedTx.value !== 0n,
    gasLimit: String(populatedTx.gasLimit || 350000n),
  });
  if (!txData || txData === "0x") {
    throw new Error(
      "StreamPayment createStream transaction encoded without calldata. Check the loaded StreamPayment ABI and wallet provider.",
    );
  }
  await preflightCreateStream(contract, createArgs);
  walletDebug("payment-stream:create:send", {
    streamPayment: spAddr,
    dataLength: txData.length,
    selector: txData.slice(0, 10),
  });
  const tx = await signer.sendTransaction({
    ...populatedTx,
    gasLimit: 350000n,
  });
  onPhase?.(
    `Waiting for ${
      purpose === "replacement" ? "replacement" : "payment"
    } stream confirmation on the blockchain`,
  );
  const receipt = await tx.wait();
  walletDebug("payment-stream:create:confirmed", {
    txHash: tx.hash,
    logCount: Array.isArray(receipt?.logs) ? receipt.logs.length : null,
  });
  const streamId = findCreatedStreamId(contract, receipt?.logs || []);
  if (!streamId) throw new Error("Stream id not found");
  walletDebug("payment-stream:create:done", { streamId: String(streamId) });

  return {
    id: String(streamId),
    contractAddress: spAddr,
    image: quotedImage,
    payment: {
      stream_id: Number(streamId),
      lease_id: quote.lease_id,
      terms_hash: quote.terms_hash,
      rate_per_second_wei: String(quote.rate_per_second_wei),
      duration_seconds: Number(quote.min_runway_seconds || durationSeconds),
    },
  };
}

async function readTokenSymbol(token: Contract): Promise<string> {
  try {
    return String(await token.symbol()) || "GLM";
  } catch {
    return "GLM";
  }
}

async function readTokenDecimals(token: Contract): Promise<number> {
  try {
    const decimals = Number(await token.decimals());
    return Number.isFinite(decimals) ? decimals : 18;
  } catch {
    return 18;
  }
}

function formatTokenAmount(value: bigint, decimals: number): string {
  const formatted = formatUnits(value, decimals);
  const [whole, fraction = ""] = formatted.split(".");
  const trimmedFraction = fraction.replace(/0+$/, "").slice(0, 6);
  return trimmedFraction ? `${whole}.${trimmedFraction}` : whole;
}

type CreateStreamArgs = readonly [
  string,
  bigint,
  bigint,
  string,
  string,
  bigint,
  string,
];

function verifyProviderQuoteSignature({
  quote,
  streamPaymentAddress,
  depositWei,
  ratePerSecondWei,
}: {
  quote: any;
  streamPaymentAddress: string;
  depositWei: bigint;
  ratePerSecondWei: bigint;
}) {
  const recovered = verifyTypedData(
    {
      name: "GolemStreamPayment",
      version: "2",
      chainId: BigInt(quote.chain_id),
      verifyingContract: streamPaymentAddress,
    },
    {
      LeaseQuote: [
        { name: "recipient", type: "address" },
        { name: "deposit", type: "uint256" },
        { name: "ratePerSecond", type: "uint128" },
        { name: "leaseId", type: "bytes32" },
        { name: "termsHash", type: "bytes32" },
        { name: "quoteExpiresAt", type: "uint128" },
      ],
    },
    {
      recipient: quote.provider_address,
      deposit: depositWei,
      ratePerSecond: ratePerSecondWei,
      leaseId: quote.lease_id,
      termsHash: quote.terms_hash,
      quoteExpiresAt: BigInt(quote.quote_expires_at),
    },
    quote.signature,
  );
  walletDebug("payment-stream:quote:signature", {
    recovered,
    expectedProvider: quote.provider_address,
    matches: recovered.toLowerCase() === quote.provider_address.toLowerCase(),
  });
  if (recovered.toLowerCase() !== quote.provider_address.toLowerCase()) {
    throw new Error(
      `Provider lease quote signature is invalid. Recovered ${recovered}, expected ${quote.provider_address}. The provider's ETHEREUM_PRIVATE_KEY must match PROVIDER_ID.`,
    );
  }
}

async function preflightCreateStream(
  contract: Contract,
  createArgs: CreateStreamArgs,
) {
  try {
    const streamId = await contract.createStream.staticCall(...createArgs);
    walletDebug("payment-stream:create:static-call:done", {
      streamId: String(streamId),
    });
  } catch (error) {
    walletWarn("payment-stream:create:static-call:failed", error, {
      selector: "createStream",
    });
    throw new Error(
      "StreamPayment createStream preflight failed before wallet submission.",
      { cause: error },
    );
  }
}

async function logCreateStreamDiagnostics({
  signer,
  contract,
  streamPaymentAddress,
  tokenAddress,
  owner,
  quote,
  depositWei,
  ratePerSecondWei,
  durationSeconds,
  resources,
  vmName,
  image,
  purpose,
  createArgs,
}: {
  signer: any;
  contract: Contract;
  streamPaymentAddress: string;
  tokenAddress: string;
  owner: string;
  quote: any;
  depositWei: bigint;
  ratePerSecondWei: bigint;
  durationSeconds: number;
  resources: VMResources;
  vmName: string;
  image: string | null;
  purpose: "new" | "replacement";
  createArgs: CreateStreamArgs;
}) {
  let chainId: string | null = null;
  let streamPaymentCode = "";
  let tokenCode = "";
  try {
    const network = await signer.provider?.getNetwork?.();
    chainId = network?.chainId == null ? null : String(network.chainId);
  } catch (error) {
    walletWarn("payment-stream:diagnostics:chain-id-failed", error);
  }
  try {
    streamPaymentCode =
      (await signer.provider?.getCode?.(streamPaymentAddress)) || "";
  } catch (error) {
    walletWarn("payment-stream:diagnostics:stream-code-failed", error, {
      streamPayment: streamPaymentAddress,
    });
  }
  try {
    tokenCode = (await signer.provider?.getCode?.(tokenAddress)) || "";
  } catch (error) {
    walletWarn("payment-stream:diagnostics:token-code-failed", error, {
      token: tokenAddress,
    });
  }

  const fragment = contract.interface.getFunction("createStream");
  walletDebug("payment-stream:create:diagnostics", {
    purpose,
    chainId,
    owner,
    vmName,
    image,
    resources,
    requestedDurationSeconds: durationSeconds,
    quoteChainId: quote.chain_id,
    streamPayment: streamPaymentAddress,
    streamPaymentCodeBytes: codeByteLength(streamPaymentCode),
    token: tokenAddress,
    tokenCodeBytes: codeByteLength(tokenCode),
    providerAddress: quote.provider_address,
    leaseId: quote.lease_id,
    termsHash: quote.terms_hash,
    quoteExpiresAt: quote.quote_expires_at,
    signatureLength: String(quote.signature || "").length,
    signaturePrefix: String(quote.signature || "").slice(0, 10),
    depositWei: String(depositWei),
    ratePerSecondWei: String(ratePerSecondWei),
    minRunwaySeconds: quote.min_runway_seconds,
    functionSelector: fragment?.selector || null,
    abiFunctionInputs: fragment?.inputs?.map((input) => input.type) || [],
    argTypes: createArgs.map((arg) => typeof arg),
  });
}

function codeByteLength(code: string) {
  if (!code || code === "0x") return 0;
  return Math.max(0, (code.length - 2) / 2);
}

function findCreatedStreamId(contract: Contract, logs: readonly unknown[]) {
  for (const rawLog of logs) {
    try {
      const parsed = contract.interface.parseLog(rawLog as any);
      if (parsed?.name === "StreamCreated") {
        return parsed.args?.[0] ?? null;
      }
    } catch {
      // Ignore logs from other contracts in the same receipt.
    }
  }
  walletDebug("payment-stream:create:event-not-found", {
    logCount: logs.length,
  });
  return null;
}

export function parseLeaseQuoteBody(body: string) {
  return JSON.parse(
    body.replace(
      /"(rate_per_second_wei|min_deposit_wei)"\s*:\s*(-?\d+)/g,
      '"$1":"$2"',
    ),
  );
}

async function createLeaseQuote(providerEndpointUrl: string, payload: any) {
  let response: Response;
  try {
    response = await fetch(`${providerEndpointUrl}/api/v1/payments/lease-quotes`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch (error) {
    walletWarn("payment-stream:quote:fetch-failed", error, {
      providerEndpointUrl,
    });
    throw new Error(
      `Provider ${providerEndpointUrl} is unreachable while loading the lease quote.`,
      { cause: error },
    );
  }
  const body = await response.text();
  walletDebug("payment-stream:quote:response", {
    providerEndpointUrl,
    status: response.status,
    ok: response.ok,
  });
  if (!response.ok) {
    walletDebug("payment-stream:quote:error-body", {
      status: response.status,
      body: body.slice(0, 500),
    });
    throw new Error(body || `Lease quote request failed with HTTP ${response.status}`);
  }
  return parseLeaseQuoteBody(body);
}
