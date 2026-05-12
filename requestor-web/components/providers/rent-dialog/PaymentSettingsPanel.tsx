"use client";

import React from "react";
import {
  RiCheckboxCircleLine,
  RiCloseCircleLine,
  RiErrorWarningLine,
  RiGlobalLine,
  RiWallet3Line,
} from "@remixicon/react";
import type { WalletNetworkStatus } from "../../../context/WalletContext";
import { Spinner } from "../../ui/Spinner";
import { cn } from "../../ui/cn";
import { SectionCard } from "./SectionCard";

export function PaymentSettingsPanel({
  walletConnected,
  paymentReady,
  paymentMessage,
  connecting,
  networkStatus,
  chainName,
  error,
  onPaymentAction,
}: {
  walletConnected: boolean;
  paymentReady: boolean;
  paymentMessage: string | null;
  connecting: boolean;
  networkStatus: WalletNetworkStatus;
  chainName: string;
  error: string | null;
  onPaymentAction: () => void;
}) {
  const actionLabel = walletConnected ? "Switch network" : "Connect";
  const busy = connecting || networkStatus === "switching";

  return (
    <SectionCard title="5. Payment settings">
      <div className="grid gap-3 sm:grid-cols-2">
        <PaymentMode active title="GLM" badge="G" />
        <PaymentMode title="ETH gas" />
      </div>

      <div className="mt-5 space-y-3">
        <StatusRow
          icon={<RiWallet3Line className="h-4 w-4" aria-hidden />}
          label="Wallet"
          value={paymentReady ? "Connected" : "Not connected"}
          tone={paymentReady ? "success" : "danger"}
          action={
            !paymentReady ? (
              <button className="btn btn-secondary h-8 px-3" type="button" disabled={busy} onClick={onPaymentAction}>
                {busy ? <Spinner className="mr-2 h-4 w-4" /> : null}
                {actionLabel}
              </button>
            ) : null
          }
        />
        <StatusRow
          icon={<RiCheckboxCircleLine className="h-4 w-4" aria-hidden />}
          label="StreamPayment contract"
          value="Available"
          tone="success"
        />
        <StatusRow
          icon={<RiGlobalLine className="h-4 w-4" aria-hidden />}
          label="Network"
          value={chainName}
          tone={paymentReady ? "success" : "neutral"}
        />
      </div>

      {!paymentReady ? (
        <div className="mt-5 rounded-md border border-danger bg-danger-soft p-4">
          <div className="flex gap-3">
            <RiErrorWarningLine className="h-5 w-5 shrink-0 text-danger" aria-hidden />
            <div>
              <div className="text-sm font-semibold text-danger">Action required</div>
              <div className="mt-2 text-sm text-danger">{paymentMessage}</div>
            </div>
          </div>
        </div>
      ) : null}

      {error ? (
        <div className="mt-4 rounded-md border border-danger bg-danger-soft p-3 text-sm text-danger">
          {error}
        </div>
      ) : null}
    </SectionCard>
  );
}

function PaymentMode({
  title,
  badge,
  active = false,
}: {
  title: string;
  badge?: string;
  active?: boolean;
}) {
  return (
    <div
      className={cn(
        "flex min-h-12 items-center gap-3 rounded-md border border-border bg-surface px-4 py-3",
        active && "border-primary ring-1 ring-primary",
        !active && "opacity-60",
      )}
    >
      {badge ? (
        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-success text-xs font-semibold text-white">
          {badge}
        </span>
      ) : (
        <span className="h-4 w-4 rounded-full border border-border-strong" aria-hidden />
      )}
      <span className="text-sm font-semibold text-text-primary">{title}</span>
    </div>
  );
}

function StatusRow({
  icon,
  label,
  value,
  tone,
  action,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  tone: "success" | "danger" | "neutral";
  action?: React.ReactNode;
}) {
  return (
    <div className="flex min-h-10 items-center gap-3 rounded-md border border-border bg-surface px-3 py-2 text-sm">
      <span className="text-text-secondary">{icon}</span>
      <span className="min-w-0 flex-1 text-text-secondary">{label}</span>
      <span
        className={cn(
          "font-medium",
          tone === "success" && "text-success",
          tone === "danger" && "text-danger",
          tone === "neutral" && "text-text-secondary",
        )}
      >
        {value}
      </span>
      {action}
      {tone === "success" ? <RiCheckboxCircleLine className="h-4 w-4 text-success" aria-hidden /> : null}
      {tone === "danger" ? <RiCloseCircleLine className="h-4 w-4 text-danger" aria-hidden /> : null}
    </div>
  );
}
