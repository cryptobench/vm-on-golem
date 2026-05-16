"use client";

import { Contract } from "ethers";
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
  ensurePaymentsNetwork: () => Promise<void>;
  onPhase?: (phase: string) => void;
};

export type OpenedPaymentStream = {
  id: string;
  contractAddress: string;
  payment: {
    stream_id: number;
    lease_id: string;
    terms_hash: string;
    rate_per_second_wei: number;
    duration_seconds: number;
  };
};

export async function openPaymentStream({
  provider,
  resources,
  durationSeconds,
  ads,
  account,
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
  walletDebug("payment-stream:quote:start", {
    providerId: provider.provider_id,
    providerUrl,
    requestor: owner,
  });
  const quote = await createLeaseQuote(providerUrl, {
    vm_name: "web-rental",
    image: "24.04",
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
  onPhase?.(
    `Waiting for your approval in ${walletName} to create the replacement stream`,
  );
  walletDebug("payment-stream:create:start", {
    streamPayment: spAddr,
    providerAddress: quote.provider_address,
    depositWei: String(depositWei),
    ratePerSecondWei: String(ratePerSecondWei),
  });
  const tx = await contract.createStream(
    quote.provider_address,
    depositWei,
    ratePerSecondWei,
    quote.lease_id,
    quote.terms_hash,
    BigInt(quote.quote_expires_at),
    quote.signature,
    { gasLimit: 350000n },
  );
  onPhase?.("Waiting for replacement stream confirmation on the blockchain");
  const receipt = await tx.wait();
  walletDebug("payment-stream:create:confirmed", {
    txHash: tx.hash,
    logCount: Array.isArray(receipt?.logs) ? receipt.logs.length : null,
  });
  const event = receipt?.logs?.find?.(
    (log: any) => String(log?.fragment?.name) === "StreamCreated",
  );
  const streamId = event?.args?.[0] ?? null;
  if (!streamId) throw new Error("Stream id not found");
  walletDebug("payment-stream:create:done", { streamId: String(streamId) });

  return {
    id: String(streamId),
    contractAddress: spAddr,
    payment: {
      stream_id: Number(streamId),
      lease_id: quote.lease_id,
      terms_hash: quote.terms_hash,
      rate_per_second_wei: Number(quote.rate_per_second_wei),
      duration_seconds: Number(quote.min_runway_seconds || durationSeconds),
    },
  };
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
  walletDebug("payment-stream:quote:response", {
    providerEndpointUrl,
    status: response.status,
    ok: response.ok,
  });
  if (!response.ok) {
    const body = await response.text();
    walletDebug("payment-stream:quote:error-body", {
      status: response.status,
      body: body.slice(0, 500),
    });
    throw new Error(body || `Lease quote request failed with HTTP ${response.status}`);
  }
  return response.json();
}
