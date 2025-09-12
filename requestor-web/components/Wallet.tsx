"use client";
import React from "react";
import { useWallet } from "../context/WalletContext";
import { MetaMaskLogo } from "./ui/MetaMaskLogo";

export function Wallet() {
  const { isInstalled, isConnected, account, connect } = useWallet();
  const label = account
    ? `${account.slice(0, 12)}…${account.slice(-8)}`
    : "";
  if (!isInstalled) {
    return (
      <button onClick={() => alert('MetaMask not detected')} className="btn btn-secondary w-full inline-flex items-center justify-center gap-2">
        <MetaMaskLogo />
        Install MetaMask
      </button>
    );
  }
  if (!isConnected) {
    return (
      <button onClick={connect} className="btn btn-primary w-full inline-flex items-center justify-center gap-2">
        <MetaMaskLogo />
        Connect
      </button>
    );
  }
  return (
    <span className="w-full inline-flex items-center justify-center gap-2 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm">
      <MetaMaskLogo />
      {label}
    </span>
  );
}
