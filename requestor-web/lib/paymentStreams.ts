"use client";

import { BrowserProvider, Contract, parseUnits } from "ethers";
import streamPayment from "../public/abi/StreamPayment.json";
import erc20 from "../public/abi/ERC20.json";
import {
  computeEstimate,
  loadSettings,
  providerInfo,
  type AdsConfig,
  type ProviderAd,
  type VMResources,
} from "./api";
import { PAYMENT_PRICE_MAX_AGE_MS, usdToTokenAsync } from "./prices";

const ZERO_ADDRESS = "0x0000000000000000000000000000000000000000";

export type OpenPaymentStreamOptions = {
  provider: Pick<ProviderAd, "provider_id" | "pricing">;
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
  await ensurePaymentsNetwork();
  const { ethereum } = window as any;
  if (!ethereum) throw new Error("MetaMask not detected");

  onPhase?.("Loading provider payment settings");
  const providerPayment = await loadProviderPaymentMetadata(
    provider.provider_id,
    ads,
  );
  const cfg = loadSettings();
  const spAddr = (
    providerPayment?.stream_payment_address ||
    cfg.stream_payment_address ||
    process.env.NEXT_PUBLIC_STREAM_PAYMENT_ADDRESS ||
    ""
  ).trim();
  if (!spAddr) {
    throw new Error(
      "StreamPayment address missing (set in Settings or provided by provider)",
    );
  }

  const token = [
    providerPayment?.glm_token_address,
    cfg.glm_token_address,
    process.env.NEXT_PUBLIC_GLM_TOKEN_ADDRESS,
  ]
    .map((value) => String(value || "").trim())
    .find((value) => value && value.toLowerCase() !== ZERO_ADDRESS);
  if (!token) {
    throw new Error(
      "GLM token address missing (set in Settings or provided by provider)",
    );
  }

  const browserProvider = new BrowserProvider(ethereum);
  const signer = await browserProvider.getSigner(account ?? undefined);
  const glm = new Contract(token, (erc20 as any).abi, signer);
  onPhase?.("Calculating replacement stream rate");
  const decimals = Number(await glm.decimals().catch(() => 18));
  const ratePerSecondWei = await computeRatePerSecondWei(
    provider,
    resources,
    decimals,
  );
  const depositWei = ratePerSecondWei * BigInt(Math.max(1, durationSeconds));

  const owner = await signer.getAddress();
  onPhase?.("Checking GLM allowance");
  const allowance = await glm.allowance(owner, spAddr);
  if (allowance < depositWei) {
    onPhase?.(
      `Waiting for your approval in ${walletName} to approve GLM spending`,
    );
    const approveTx = await glm.approve(spAddr, depositWei);
    onPhase?.("Waiting for GLM approval confirmation on the blockchain");
    await approveTx.wait();
  }

  const contract = new Contract(spAddr, (streamPayment as any).abi, signer);
  onPhase?.(
    `Waiting for your approval in ${walletName} to create the replacement stream`,
  );
  const tx = await contract.createStream(
    token,
    provider.provider_id,
    depositWei,
    ratePerSecondWei,
    { gasLimit: 350000n },
  );
  onPhase?.("Waiting for replacement stream confirmation on the blockchain");
  const receipt = await tx.wait();
  const event = receipt?.logs?.find?.(
    (log: any) => String(log?.fragment?.name) === "StreamCreated",
  );
  const streamId = event?.args?.[0] ?? null;
  if (!streamId) throw new Error("Stream id not found");

  return { id: String(streamId), contractAddress: spAddr };
}

function getWalletName() {
  const ethereum = (window as any)?.ethereum;
  if (ethereum?.isMetaMask) return "MetaMask";
  if (ethereum?.isRabby) return "Rabby";
  if (ethereum?.isBraveWallet) return "Brave Wallet";
  return "your wallet";
}

async function loadProviderPaymentMetadata(providerId: string, ads: AdsConfig) {
  try {
    return await providerInfo(providerId, ads);
  } catch (error) {
    console.warn(
      "Provider payment metadata unavailable, using local payment settings",
      error,
    );
    return null;
  }
}

async function computeRatePerSecondWei(
  provider: Pick<ProviderAd, "pricing">,
  resources: VMResources,
  decimals: number,
) {
  const estimate = computeEstimate(
    provider as ProviderAd,
    resources.cpu,
    resources.memory,
    resources.storage,
  );
  let glmPerMonth: number | null = estimate.glm_per_month ?? null;
  if (glmPerMonth == null) {
    glmPerMonth = await usdToTokenAsync("GLM", estimate.usd_per_month, {
      maxAgeMs: PAYMENT_PRICE_MAX_AGE_MS,
    });
    if (glmPerMonth == null) {
      throw new Error("GLM/USD price unavailable to compute rate");
    }
  }

  const glmPerSecond = glmPerMonth / (30.4167 * 24 * 3600);
  const ratePerSecondWei = parseUnits(glmPerSecond.toFixed(decimals), decimals);
  if (ratePerSecondWei <= 0n) {
    throw new Error("Computed GLM rate is too small");
  }
  return ratePerSecondWei;
}
