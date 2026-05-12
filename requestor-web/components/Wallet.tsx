"use client";
import React from "react";
import { useWallet } from "../context/WalletContext";
import { MetaMaskLogo } from "./ui/MetaMaskLogo";
import { Spinner } from "./ui/Spinner";

export function Wallet() {
  const {
    isInstalled,
    isConnected,
    account,
    expectedChain,
    networkStatus,
    networkError,
    connect,
    switchToPaymentsNetwork,
  } = useWallet();
  const [busy, setBusy] = React.useState(false);
  const label = account
    ? `${account.slice(0, 12)}...${account.slice(-8)}`
    : "";

  const run = async (action: () => Promise<void>) => {
    setBusy(true);
    try {
      await action();
    } catch {
      // The shared wallet state stores the actionable error message.
    } finally {
      setBusy(false);
    }
  };

  if (!isInstalled) {
    return (
      <button
        onClick={() => window.open("https://metamask.io/download/", "_blank", "noopener,noreferrer")}
        className="btn btn-secondary w-full inline-flex items-center justify-center gap-2"
      >
        <MetaMaskLogo />
        Install MetaMask
      </button>
    );
  }

  if (!isConnected) {
    return (
      <button
        onClick={() => run(connect)}
        className="btn btn-primary w-full inline-flex items-center justify-center gap-2"
        disabled={busy || networkStatus === "switching"}
      >
        {busy || networkStatus === "switching" ? <Spinner className="h-4 w-4 text-white" /> : <MetaMaskLogo />}
        Connect wallet
      </button>
    );
  }

  if (networkStatus !== "ready") {
    const message = networkError || `Switch to ${expectedChain.chainName}`;
    return (
      <div className="space-y-2">
        <button
          onClick={() => run(switchToPaymentsNetwork)}
          className="btn btn-primary w-full inline-flex items-center justify-center gap-2"
          disabled={busy || networkStatus === "switching"}
          title={message}
        >
          {busy || networkStatus === "switching" ? <Spinner className="h-4 w-4 text-white" /> : <MetaMaskLogo />}
          {networkStatus === "rpc_error" ? "Update RPC" : "Switch Network"}
        </button>
        <div className="text-xs text-text-secondary">{message}</div>
      </div>
    );
  }

  return (
    <span className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-border bg-surface px-3 py-1.5 text-sm">
      <MetaMaskLogo />
      {label}
    </span>
  );
}
