"use client";

import { BrowserProvider } from "ethers";
import {
  getPaymentsChain,
  PaymentNetworkError,
  switchToPaymentsNetwork,
  type PaymentsChain,
} from "./chain";
import { walletDebug, walletWarn } from "./walletDebug";

export type PaymentsWalletOptions = {
  account?: string | null;
  chain?: PaymentsChain;
  ensurePaymentsNetwork?: () => Promise<void>;
};

export function getInjectedEthereum() {
  if (typeof window === "undefined") return null;
  const ethereum = (window as any).ethereum;
  if (!ethereum?.request) return null;
  const providers = Array.isArray(ethereum.providers)
    ? ethereum.providers
    : [];
  const selected =
    providers.find((provider: any) => provider?.isMetaMask) ||
    providers.find((provider: any) => provider?.isRabby) ||
    providers.find((provider: any) => provider?.isBraveWallet) ||
    ethereum;
  walletDebug("provider:selected", {
    providerCount: providers.length || 1,
    selected: describeWalletProvider(selected),
    available: providers.length
      ? providers.map(describeWalletProvider)
      : [describeWalletProvider(ethereum)],
  });
  return selected;
}

export async function getPaymentsEthereum({
  chain = getPaymentsChain(),
  ensurePaymentsNetwork,
}: PaymentsWalletOptions = {}) {
  if (typeof window === "undefined") {
    throw new PaymentNetworkError(
      "missing_wallet",
      "MetaMask is not available.",
    );
  }

  const ethereum = getInjectedEthereum();
  if (!ethereum?.request) {
    throw new PaymentNetworkError(
      "missing_wallet",
      "MetaMask is not available.",
    );
  }

  if (ensurePaymentsNetwork) {
    walletDebug("prepare:context-ensure:start", { chainId: chain.chainId });
    try {
      await ensurePaymentsNetwork();
      walletDebug("prepare:context-ensure:done", { chainId: chain.chainId });
    } catch (error) {
      walletWarn("prepare:context-ensure:failed", error, {
        chainId: chain.chainId,
      });
      throw error;
    }
  }
  walletDebug("prepare:switch:start", {
    chainId: chain.chainId,
    rpcUrl: chain.rpcUrls[0],
  });
  try {
    await switchToPaymentsNetwork(ethereum, chain);
    walletDebug("prepare:switch:done", { chainId: chain.chainId });
  } catch (error) {
    walletWarn("prepare:switch:failed", error, {
      chainId: chain.chainId,
      rpcUrl: chain.rpcUrls[0],
    });
    throw error;
  }

  return ethereum;
}

export async function getPaymentsBrowserProvider(
  options: PaymentsWalletOptions = {},
) {
  return new BrowserProvider(await getPaymentsEthereum(options));
}

export async function getPaymentsSigner(options: PaymentsWalletOptions = {}) {
  const provider = await getPaymentsBrowserProvider(options);
  return provider.getSigner(options.account ?? undefined);
}

export function getWalletName(ethereum?: any) {
  const wallet =
    ethereum ??
    getInjectedEthereum();
  if (wallet?.isMetaMask) return "MetaMask";
  if (wallet?.isRabby) return "Rabby";
  if (wallet?.isBraveWallet) return "Brave Wallet";
  return "your wallet";
}

function describeWalletProvider(provider: any) {
  return {
    isMetaMask: Boolean(provider?.isMetaMask),
    isRabby: Boolean(provider?.isRabby),
    isBraveWallet: Boolean(provider?.isBraveWallet),
    isCoinbaseWallet: Boolean(provider?.isCoinbaseWallet),
  };
}
