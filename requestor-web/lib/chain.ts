"use client";

export type PaymentsChain = {
  chainId: string;
  chainName: string;
  nativeCurrency: { name: string; symbol: string; decimals: number };
  rpcUrls: string[];
  blockExplorerUrls?: string[];
};

export function getPaymentsChain(): PaymentsChain {
  const chainId = process.env.NEXT_PUBLIC_EVM_CHAIN_ID || "0x4268";
  return {
    chainId,
    chainName: process.env.NEXT_PUBLIC_EVM_CHAIN_NAME || "Golem Payments",
    nativeCurrency: { name: "ETH", symbol: "ETH", decimals: 18 },
    rpcUrls: [process.env.NEXT_PUBLIC_EVM_RPC_URL || "http://localhost:8545"],
  };
}

export async function ensureNetwork(ethereum: any, chain: PaymentsChain) {
  if (!ethereum?.request) throw new Error("wallet unavailable");
  const current = await ethereum.request({ method: "eth_chainId" }).catch(() => null);
  if (String(current).toLowerCase() === chain.chainId.toLowerCase()) return;
  try {
    await ethereum.request({
      method: "wallet_switchEthereumChain",
      params: [{ chainId: chain.chainId }],
    });
  } catch (error: any) {
    if (error?.code !== 4902) throw error;
    await ethereum.request({
      method: "wallet_addEthereumChain",
      params: [chain],
    });
  }
}
