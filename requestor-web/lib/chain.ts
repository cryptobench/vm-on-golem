"use client";

import { loadSettings, type Settings } from "./settings";
import { getRequestorRuntimeConfig } from "./runtimeConfig";
import { walletDebug, walletWarn } from "./walletDebug";

const DEFAULT_CHAIN_ID = "0x88bb0";
const DEFAULT_CHAIN_NAME = "Ethereum Hoodi";
const DEFAULT_RPC_URL = "https://rpc.hoodi.ethpandaops.io";
const DEFAULT_EXPLORER_URL = "https://hoodi.etherscan.io";

export type PaymentsChain = {
  chainId: string;
  chainName: string;
  nativeCurrency: { name: string; symbol: string; decimals: number };
  rpcUrls: string[];
  blockExplorerUrls?: string[];
};

export type PaymentNetworkErrorCode =
  | "missing_wallet"
  | "rpc_unhealthy"
  | "user_rejected"
  | "wrong_network"
  | "switch_failed";

export class PaymentNetworkError extends Error {
  code: PaymentNetworkErrorCode;
  cause?: unknown;

  constructor(code: PaymentNetworkErrorCode, message: string, cause?: unknown) {
    super(message);
    this.name = "PaymentNetworkError";
    this.code = code;
    this.cause = cause;
  }
}

export function normalizeChainId(
  value: string | number | null | undefined,
  fallback = DEFAULT_CHAIN_ID,
): string {
  if (typeof value === "number" && Number.isFinite(value) && value > 0) {
    return `0x${Math.floor(value).toString(16)}`;
  }

  const text = String(value || "").trim().toLowerCase();
  if (!text) return fallback.toLowerCase();

  const parsed = text.startsWith("0x")
    ? Number.parseInt(text.slice(2), 16)
    : Number.parseInt(text, 10);
  if (Number.isFinite(parsed) && parsed > 0) {
    return `0x${parsed.toString(16)}`;
  }

  return fallback.toLowerCase();
}

export function getPaymentsChain(settings: Partial<Settings> = loadSettings()): PaymentsChain {
  const runtimeConfig = getRequestorRuntimeConfig();
  const chainId = normalizeChainId(
    settings.evm_chain_id || runtimeConfig.evmChainId,
  );
  const rpcUrl = (
    settings.evm_rpc_url ||
    runtimeConfig.evmRpcUrl ||
    DEFAULT_RPC_URL
  ).trim();
  const explorerUrl = (
    settings.evm_explorer_url ||
    runtimeConfig.evmExplorerUrl ||
    DEFAULT_EXPLORER_URL
  ).trim();

  return {
    chainId,
    chainName:
      settings.evm_chain_name ||
      runtimeConfig.evmChainName ||
      DEFAULT_CHAIN_NAME,
    nativeCurrency: { name: "ETH", symbol: "ETH", decimals: 18 },
    rpcUrls: [rpcUrl],
    blockExplorerUrls: explorerUrl ? [explorerUrl] : undefined,
  };
}

export function isExpectedPaymentsChain(
  currentChainId: string | number | null | undefined,
  expected: PaymentsChain = getPaymentsChain(),
): boolean {
  return normalizeChainId(currentChainId) === normalizeChainId(expected.chainId);
}

export async function ensureNetwork(
  ethereum: any,
  chain: PaymentsChain = getPaymentsChain(),
): Promise<void> {
  await switchToPaymentsNetwork(ethereum, chain);
}

export async function requirePaymentsNetwork(
  ethereum: any,
  chain: PaymentsChain = getPaymentsChain(),
): Promise<void> {
  if (!ethereum?.request) {
    throw new PaymentNetworkError("missing_wallet", "MetaMask is not available.");
  }
  const current = await readWalletChainId(ethereum);
  if (!isExpectedPaymentsChain(current, chain)) {
    throw new PaymentNetworkError(
      "wrong_network",
      `MetaMask is not connected to ${chain.chainName}.`,
    );
  }
}

export async function switchToPaymentsNetwork(
  ethereum: any,
  chain: PaymentsChain = getPaymentsChain(),
): Promise<void> {
  if (!ethereum?.request) {
    throw new PaymentNetworkError("missing_wallet", "MetaMask is not available.");
  }

  walletDebug("network:switch:start", {
    expectedChainId: chain.chainId,
    chainName: chain.chainName,
    rpcUrl: chain.rpcUrls[0],
  });
  let current = await readWalletChainIdOrNull(ethereum);
  walletDebug("network:current-chain", {
    currentChainId: current,
    expectedChainId: chain.chainId,
  });
  if (!isExpectedPaymentsChain(current, chain)) {
    await requestPaymentsNetworkSwitch(ethereum, chain);
  }

  const next = await readWalletChainId(ethereum);
  walletDebug("network:post-switch-chain", {
    currentChainId: next,
    expectedChainId: chain.chainId,
  });
  if (!isExpectedPaymentsChain(next, chain)) {
    throw new PaymentNetworkError(
      "wrong_network",
      `MetaMask is not connected to ${chain.chainName}.`,
    );
  }
}

async function addOrUpdatePaymentsNetwork(
  ethereum: any,
  chain: PaymentsChain,
  cause?: unknown,
): Promise<void> {
  try {
    walletDebug("network:add:start", {
      chainId: chain.chainId,
      rpcUrl: chain.rpcUrls[0],
    });
    await ethereum.request({
      method: "wallet_addEthereumChain",
      params: [chain],
    });
    walletDebug("network:add:done", { chainId: chain.chainId });
  } catch (error: any) {
    walletWarn("network:add:failed", error, { chainId: chain.chainId });
    if (error?.code === 4001) {
      throw new PaymentNetworkError(
        "user_rejected",
        `Adding ${chain.chainName} was rejected.`,
        error,
      );
    }
    throw new PaymentNetworkError(
      "switch_failed",
      `Could not add or update ${chain.chainName} in MetaMask.`,
      cause || error,
    );
  }
}

async function requestPaymentsNetworkSwitch(
  ethereum: any,
  chain: PaymentsChain,
): Promise<void> {
  try {
    walletDebug("network:switch-request:start", { chainId: chain.chainId });
    await ethereum.request({
      method: "wallet_switchEthereumChain",
      params: [{ chainId: chain.chainId }],
    });
    walletDebug("network:switch-request:done", { chainId: chain.chainId });
  } catch (error: any) {
    walletWarn("network:switch-request:failed", error, {
      chainId: chain.chainId,
    });
    if (error?.code === 4001) {
      throw new PaymentNetworkError(
        "user_rejected",
        `Switch to ${chain.chainName} was rejected.`,
        error,
      );
    }
    if (error?.code !== 4902) {
      throw new PaymentNetworkError(
        "switch_failed",
        `Could not switch MetaMask to ${chain.chainName}.`,
        error,
      );
    }
    await addOrUpdatePaymentsNetwork(ethereum, chain, error);
    walletDebug("network:switch-after-add:start", { chainId: chain.chainId });
    await ethereum.request({
      method: "wallet_switchEthereumChain",
      params: [{ chainId: chain.chainId }],
    });
    walletDebug("network:switch-after-add:done", { chainId: chain.chainId });
  }
}

async function readWalletChainIdOrNull(ethereum: any): Promise<string | null> {
  try {
    return await readWalletChainId(ethereum);
  } catch {
    return null;
  }
}

export async function readWalletChainId(ethereum: any): Promise<string> {
  try {
    const chainId = await ethereum.request({ method: "eth_chainId" });
    walletDebug("network:read-chain:done", { chainId });
    return normalizeChainId(chainId);
  } catch (error) {
    walletWarn("network:read-chain:failed", error);
    throw new PaymentNetworkError(
      "rpc_unhealthy",
      "MetaMask cannot reach the payments RPC endpoint.",
      error,
    );
  }
}

export function getPaymentNetworkErrorMessage(
  error: unknown,
  chain: PaymentsChain = getPaymentsChain(),
): string {
  const paymentError = toPaymentNetworkError(error);
  walletDebug("network:error-message", {
    code: paymentError?.code || null,
    chainName: chain.chainName,
    rpcUrl: chain.rpcUrls[0],
  });
  if (paymentError?.code === "missing_wallet") {
    return "MetaMask is required for payment streams.";
  }
  if (paymentError?.code === "user_rejected") {
    return paymentError.message;
  }
  if (paymentError?.code === "wrong_network") {
    return `Switch MetaMask to ${chain.chainName} before continuing.`;
  }
  if (paymentError?.code === "rpc_unhealthy") {
    return `MetaMask cannot reach ${chain.chainName}. Use MetaMask's Update RPC option or set the RPC URL to ${chain.rpcUrls[0]}.`;
  }
  if (paymentError?.code === "switch_failed") {
    return `Could not switch MetaMask to ${chain.chainName}. Check the network settings and retry.`;
  }

  if (typeof error === "object" && error !== null) {
    const value = error as {
      message?: unknown;
      reason?: unknown;
      shortMessage?: unknown;
      code?: unknown;
    };
    const message =
      value.shortMessage || value.reason || value.message || value.code;
    if (message) return String(message);
  }

  return error instanceof Error ? error.message : String(error);
}

export function toPaymentNetworkError(error: unknown): PaymentNetworkError | null {
  if (error instanceof PaymentNetworkError) return error;
  if (typeof error === "object" && error !== null && "code" in error) {
    const code = (error as { code?: unknown }).code;
    if (code === 4001) {
      return new PaymentNetworkError(
        "user_rejected",
        "The wallet request was rejected.",
        error,
      );
    }
  }
  if (looksLikeWalletRpcFailure(error)) {
    return new PaymentNetworkError(
      "rpc_unhealthy",
      "MetaMask cannot reach the payments RPC endpoint.",
      error,
    );
  }
  return null;
}

function looksLikeWalletRpcFailure(error: unknown): boolean {
  const text = collectErrorText(error).toLowerCase();
  return (
    text.includes("rpc endpoint returned too many errors") ||
    text.includes("could not coalesce error")
  );
}

function collectErrorText(error: unknown): string {
  if (error == null) return "";
  if (typeof error === "string") return error;
  if (error instanceof Error) {
    const cause = (error as Error & { cause?: unknown }).cause;
    return `${error.message} ${collectErrorText(cause)}`;
  }
  if (typeof error === "object") {
    try {
      return JSON.stringify(error);
    } catch {
      return String(error);
    }
  }
  return String(error);
}
