"use client";

import React from "react";
import { RiArrowDownSLine, RiWallet3Line } from "@remixicon/react";
import { useWallet } from "../../context/WalletContext";
import { useToast } from "@golem/ui";
import { Spinner } from "@golem/ui";
import { cn } from "@golem/ui";

function shortAccount(account: string | null) {
  return account
    ? `${account.slice(0, 6)}...${account.slice(-4)}`
    : "Not connected";
}

export function WalletStatusButton() {
  const {
    isInstalled,
    isConnected,
    account,
    networkStatus,
    networkError,
    connect,
    switchToPaymentsNetwork,
  } = useWallet();
  const { show } = useToast();
  const [busy, setBusy] = React.useState(false);

  const connectedAndReady = isConnected && networkStatus === "ready";
  const label = !isInstalled
    ? "MetaMask needed"
    : connectedAndReady
      ? shortAccount(account)
      : isConnected
        ? "Wrong network"
        : "Not connected";

  const action = async () => {
    if (!isInstalled) {
      window.open(
        "https://metamask.io/download/",
        "_blank",
        "noopener,noreferrer",
      );
      return;
    }
    setBusy(true);
    try {
      if (!isConnected) {
        await connect();
      } else if (networkStatus !== "ready") {
        await switchToPaymentsNetwork();
      }
    } catch (error) {
      show(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  };

  return (
    <button
      className="btn btn-secondary min-w-44 justify-between gap-3 px-4"
      onClick={action}
      type="button"
      title={networkError || label}
      disabled={busy || networkStatus === "switching"}
    >
      <span className="flex min-w-0 items-center gap-2">
        {busy || networkStatus === "switching" ? (
          <Spinner className="h-4 w-4 text-primary" />
        ) : (
          <RiWallet3Line
            className="h-5 w-5 shrink-0 text-text-secondary"
            aria-hidden
          />
        )}
        <span
          className={cn(
            "truncate",
            connectedAndReady ? "text-text-primary" : "text-danger",
          )}
        >
          {label}
        </span>
      </span>
      <RiArrowDownSLine
        className="h-5 w-5 shrink-0 text-text-secondary"
        aria-hidden
      />
    </button>
  );
}
