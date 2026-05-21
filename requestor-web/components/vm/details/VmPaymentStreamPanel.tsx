"use client";

import React from "react";
import { RiArrowDownSLine, RiExternalLinkLine } from "@remixicon/react";
import type { ChainStream } from "../../../lib/streams";
import { humanDuration, isTerminatedStream } from "../../../lib/streams";
import { formatUnixSecondsDateTime } from "../../../lib/time";
import { Button } from "@golem/ui";
import {
  CopyInline,
  DetailPanel,
  PanelTitle,
  shortAddress,
} from "./VmDetailPrimitives";

export function VmPaymentStreamPanel({
  streamId,
  stream,
  remaining,
  tokenSymbol,
  tokenDecimals,
  usdPrice,
  displayCurrency,
  busy,
  actionsDisabled,
  actionsDisabledReason,
  explorerUrl,
  onCopy,
  onTopUp,
}: {
  streamId?: string | number | null;
  stream: ChainStream;
  remaining: number;
  tokenSymbol: string;
  tokenDecimals: number;
  usdPrice: number | null;
  displayCurrency: "fiat" | "token";
  busy?: boolean;
  actionsDisabled?: boolean;
  actionsDisabledReason?: string | null;
  explorerUrl?: string | null;
  onCopy: (value: string) => void;
  onTopUp: (seconds: number) => void;
}) {
  const values = streamValues(
    stream,
    remaining,
    tokenDecimals,
    tokenSymbol,
    usdPrice,
  );
  const terminated = isTerminatedStream(stream);
  const disabled = !!busy || !!actionsDisabled || terminated;

  return (
    <DetailPanel className="vm-page-enter">
      <PanelTitle
        title="Payment stream"
        trailing={
          <span className="rounded-md bg-success-soft px-2 py-1 text-xs font-medium text-success">
            {terminated ? "Terminated" : "Active"}
          </span>
        }
      />

      <div className="mt-5 space-y-5">
        <div>
          <div className="text-xs font-medium text-text-muted">Stream ID</div>
          <div className="mt-2 text-sm font-medium text-text-primary">
            <CopyInline
              value={streamId}
              display={shortAddress(streamId)}
              onCopy={onCopy}
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-x-4 gap-y-5 border-y border-border py-4">
          <Stat label="Remaining time" value={humanDuration(remaining)} />
          <Stat
            label="Spent so far"
            value={
              displayCurrency === "fiat" && values.spentUsd != null
                ? `$${values.spentUsd.toFixed(2)}`
                : `${values.spentToken.toFixed(4)} ${tokenSymbol}`
            }
          />
          <Stat
            label="Remaining balance"
            value={
              displayCurrency === "fiat" && values.remainingUsd != null
                ? `$${values.remainingUsd.toFixed(2)}`
                : `${values.remainingToken.toFixed(4)} ${tokenSymbol}`
            }
          />
          <Stat
            label="Hourly rate"
            value={`${values.hourlyToken.toFixed(4)} ${tokenSymbol}`}
          />
        </div>

        {actionsDisabledReason && (
          <div className="rounded-md border border-warning bg-warning-soft p-3 text-sm text-text-primary">
            {actionsDisabledReason}
          </div>
        )}

        <div className="grid gap-3 sm:grid-cols-2">
          <Button
            variant="primary"
            busy={!!busy}
            disabled={disabled}
            onClick={() => onTopUp(3600)}
          >
            Top up stream
          </Button>
          <a
            className={`btn btn-secondary gap-2 ${!explorerUrl ? "pointer-events-none opacity-45" : ""}`}
            href={explorerUrl || "#"}
            target="_blank"
            rel="noreferrer"
            aria-disabled={!explorerUrl}
          >
            View on-chain
            <RiExternalLinkLine className="h-4 w-4" aria-hidden />
          </a>
        </div>

        <details className="group border-t border-border pt-4">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-sm font-semibold text-text-primary">
            On-chain details
            <RiArrowDownSLine
              className="h-5 w-5 text-text-muted transition group-open:rotate-180"
              aria-hidden
            />
          </summary>
          <dl className="mt-3 space-y-2 text-sm">
            <Row
              label="Token"
              value={`${tokenSymbol} (${tokenDecimals} decimals)`}
            />
            <Row
              label="Recipient (Provider ID)"
              value={
                <CopyInline
                  value={stream.recipient}
                  display={shortAddress(stream.recipient)}
                  onCopy={onCopy}
                />
              }
            />
            <Row
              label="Rate (per second)"
              value={`${values.rateToken.toFixed(8)} ${tokenSymbol}/s`}
            />
            <Row
              label="Deposit"
              value={`${values.deposit.toFixed(4)} ${tokenSymbol}`}
            />
            <Row
              label="Spent so far"
              value={`${values.spentToken.toFixed(4)} ${tokenSymbol}`}
            />
            <Row
              label="Withdrawn"
              value={`${values.withdrawn.toFixed(4)} ${tokenSymbol}`}
            />
            <Row label="Stop time" value={formatStopTime(stream.stopTime)} />
          </dl>
        </details>
      </div>
    </DetailPanel>
  );
}

function Stat({
  label,
  value,
  subValue,
}: {
  label: string;
  value: string;
  subValue?: string | null;
}) {
  return (
    <div className="min-w-0">
      <div className="text-xs text-text-muted">{label}</div>
      <div className="mt-2 truncate text-sm font-semibold text-text-primary">
        {value}
      </div>
      {subValue && (
        <div className="mt-1 truncate text-xs text-text-muted">{subValue}</div>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <dt className="text-text-secondary">{label}</dt>
      <dd className="min-w-0 text-right font-medium text-text-primary">
        {value}
      </dd>
    </div>
  );
}

function streamValues(
  stream: ChainStream,
  remaining: number,
  decimals: number,
  symbol: string,
  usdPrice: number | null,
) {
  const scale = 10 ** (decimals || 18);
  const donationMultiplier = 1 + Number(stream.donationBps || 0) / 10_000;
  const rateToken = (Number(stream.providerRatePerSecond) / scale) * donationMultiplier;
  const deposit = Number(stream.providerDeposit + stream.donationDeposit) / scale;
  const withdrawn =
    Number(stream.providerWithdrawn + stream.donationWithdrawn) / scale;
  const hourlyToken = rateToken * 3600;
  const remainingToken = Math.max(0, rateToken * remaining);
  const startTime = Number(stream.startTime || 0n);
  const stopTime = Number(stream.stopTime || 0n);
  const nowSec = Math.floor(Date.now() / 1000);
  const effectiveTime = isTerminatedStream(stream) ? stopTime : Math.min(nowSec, stopTime);
  const elapsedSeconds = Math.max(0, effectiveTime - startTime);
  const spentToken = Math.max(0, Math.min(deposit, elapsedSeconds * rateToken));
  const hourlyUsd = usdPrice == null ? null : hourlyToken * usdPrice;
  const spentUsd = usdPrice == null ? null : spentToken * usdPrice;
  const remainingUsd = usdPrice == null ? null : remainingToken * usdPrice;

  return {
    symbol,
    rateToken,
    deposit,
    withdrawn,
    hourlyToken,
    spentToken,
    remainingToken,
    hourlyUsd,
    spentUsd,
    remainingUsd,
  };
}

function formatStopTime(stopTime: bigint) {
  return formatUnixSecondsDateTime(stopTime) ?? "-";
}
