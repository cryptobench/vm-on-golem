"use client";

import { formatUnits } from "ethers";
import { loadSettings } from "./settings";
import { getRequestorRuntimeConfig } from "./runtimeConfig";

export const TGLM_MINTER_ABI = ["function create() external"] as const;

export type FundingConfig = {
  tokenAddress: string;
  minterAddress: string;
  faucetUrl: string;
  explorerUrl: string;
};

export function getFundingConfig(): FundingConfig {
  const settings = loadSettings();
  const runtime = getRequestorRuntimeConfig();
  return {
    tokenAddress: (
      settings.glm_token_address ||
      runtime.glmTokenAddress ||
      ""
    ).trim(),
    minterAddress: (runtime.tglmMinterAddress || "").trim(),
    faucetUrl: (runtime.hoodiFaucetUrl || "").trim(),
    explorerUrl: (
      settings.evm_explorer_url ||
      runtime.evmExplorerUrl ||
      ""
    ).trim(),
  };
}

export function formatTokenBalance(
  value: bigint | null,
  decimals = 18,
  symbol = "tGLM",
): string {
  if (value === null) return "Not checked";
  return `${formatCompactUnits(value, decimals)} ${symbol}`;
}

export function formatNativeBalance(value: bigint | null): string {
  if (value === null) return "Not checked";
  return `${formatCompactUnits(value, 18)} ETH`;
}

export function formatCompactUnits(value: bigint, decimals: number): string {
  const formatted = formatUnits(value, decimals);
  const [whole, fraction = ""] = formatted.split(".");
  const trimmed = fraction.replace(/0+$/, "").slice(0, 6);
  return trimmed ? `${whole}.${trimmed}` : whole;
}

export function explorerTxUrl(explorerUrl: string, txHash: string): string {
  const base = explorerUrl.replace(/\/$/, "");
  return base && txHash ? `${base}/tx/${txHash}` : "";
}
