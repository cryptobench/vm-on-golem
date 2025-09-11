"use client";
import React from "react";
import { useWallet } from "../context/WalletContext";

export function Wallet() {
  const { isInstalled, isConnected, account, chainId, connect } = useWallet();
  return (
    <div className="flex items-center gap-3">
      {!isInstalled ? (
        <button onClick={() => alert('MetaMask not detected')} className="btn btn-secondary">No MetaMask</button>
      ) : isConnected ? (
        <>
          <span className="inline-flex items-center rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm">
            Wallet: {account?.slice(0, 6)}…{account?.slice(-4)}
          </span>
          <span className="text-sm text-gray-600">Chain: {chainId || '—'}</span>
        </>
      ) : (
        <button onClick={connect} className="btn btn-primary">Connect MetaMask</button>
      )}
    </div>
  );
}
