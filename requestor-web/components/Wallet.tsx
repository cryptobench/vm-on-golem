"use client";
import React from "react";
import { BrowserProvider } from "ethers";

export function Wallet() {
  const [account, setAccount] = React.useState<string | null>(null);
  const [chainId, setChainId] = React.useState<string | null>(null);

  const desiredChainId = (process.env.NEXT_PUBLIC_EVM_CHAIN_ID || "").toLowerCase();

  const connect = async () => {
    const { ethereum } = window as any;
    if (!ethereum) {
      alert("MetaMask not detected");
      return;
    }
    const provider = new BrowserProvider(ethereum);
    const accounts = await ethereum.request({ method: "eth_requestAccounts" });
    const network = await provider.getNetwork();
    setAccount(accounts?.[0] || null);
    setChainId("0x" + Number(network.chainId).toString(16));
    // Optionally prompt network switch
    if (desiredChainId && ("0x" + Number(network.chainId).toString(16)).toLowerCase() !== desiredChainId) {
      try {
        await ethereum.request({ method: "wallet_switchEthereumChain", params: [{ chainId: desiredChainId }] });
      } catch (e) {
        console.warn("Chain switch rejected or failed", e);
      }
    }
  };

  React.useEffect(() => {
    const { ethereum } = window as any;
    if (!ethereum) return;
    const onAccounts = (accs: string[]) => setAccount(accs?.[0] || null);
    const onChain = (cid: string) => setChainId(cid);
    ethereum.on?.("accountsChanged", onAccounts);
    ethereum.on?.("chainChanged", onChain);
    return () => {
      ethereum.removeListener?.("accountsChanged", onAccounts);
      ethereum.removeListener?.("chainChanged", onChain);
    };
  }, []);

  return (
    <div className="flex items-center gap-3">
      {account ? (
        <>
          <span className="inline-flex items-center rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm">
            Wallet: {account.slice(0, 6)}…{account.slice(-4)}
          </span>
          <span className="text-sm text-gray-600">Chain: {chainId || '—'}</span>
        </>
      ) : (
        <button onClick={connect} className="btn btn-primary">Connect MetaMask</button>
      )}
    </div>
  );
}
