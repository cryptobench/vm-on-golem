"use client";

import React from "react";
import { RiExternalLinkLine } from "@remixicon/react";
import type { ChainStream } from "../../../lib/streams";
import { humanDuration } from "../../../lib/streams";
import { Spinner } from "../../ui/Spinner";
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
  const values = streamValues(stream, remaining, tokenDecimals, tokenSymbol, usdPrice);
  const disabled = !!busy || !!actionsDisabled || stream.halted;

  return (
    <DetailPanel className="vm-page-enter">
      <PanelTitle
        title="Payment stream"
        trailing={
          <span className="rounded-md bg-success-soft px-2 py-1 text-xs font-medium text-success">
            {stream.halted ? "Halted" : "Active"}
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

        <div className="grid grid-cols-3 divide-x divide-border border-y border-border py-4">
          <Stat label="Remaining time" value={humanDuration(remaining)} />
          <Stat
            label="Remaining balance"
            value={
              displayCurrency === "fiat" && values.remainingUsd != null
                ? `$${values.remainingUsd.toFixed(2)}`
                : `${values.remainingToken.toFixed(4)} ${tokenSymbol}`
            }
            subValue={
              displayCurrency === "fiat"
                ? `${values.remainingToken.toFixed(4)} ${tokenSymbol}`
                : values.remainingUsd == null
                  ? null
                  : `$${values.remainingUsd.toFixed(2)}`
            }
          />
          <Stat
            label="Hourly rate"
            value={`${values.hourlyToken.toFixed(4)} ${tokenSymbol}`}
            subValue={
              values.hourlyUsd == null ? null : `$${values.hourlyUsd.toFixed(2)}`
            }
          />
        </div>

        {actionsDisabledReason && (
          <div className="rounded-md border border-warning bg-warning-soft p-3 text-sm text-text-primary">
            {actionsDisabledReason}
          </div>
        )}

        <div className="grid gap-3 sm:grid-cols-2">
          <button
            type="button"
            className="btn btn-primary gap-2"
            disabled={disabled}
            onClick={() => onTopUp(3600)}
          >
            {busy && <Spinner className="h-4 w-4 text-white" />}
            Top up stream
          </button>
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

        <div>
          <div className="text-sm font-semibold text-text-primary">
            On-chain stream data
          </div>
          <dl className="mt-3 space-y-2 text-sm">
            <Row label="Token" value={`${tokenSymbol} (${tokenDecimals} decimals)`} />
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
            <Row label="Deposit" value={`${values.deposit.toFixed(4)} ${tokenSymbol}`} />
            <Row
              label="Withdrawn"
              value={`${values.withdrawn.toFixed(4)} ${tokenSymbol}`}
            />
            <Row label="Stop time" value={formatStopTime(stream.stopTime)} />
            <Row
              label="Halted"
              value={
                <span className={stream.halted ? "text-danger" : "text-success"}>
                  {stream.halted ? "Yes" : "No"}
                </span>
              }
            />
          </dl>
        </div>
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
    <div className="min-w-0 px-3 first:pl-0 last:pr-0">
      <div className="text-xs text-text-muted">{label}</div>
      <div className="mt-2 truncate text-sm font-semibold text-text-primary">{value}</div>
      {subValue && <div className="mt-1 truncate text-xs text-text-muted">{subValue}</div>}
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <dt className="text-text-secondary">{label}</dt>
      <dd className="min-w-0 text-right font-medium text-text-primary">{value}</dd>
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
  const rateToken = Number(stream.ratePerSecond) / scale;
  const deposit = Number(stream.deposit) / scale;
  const withdrawn = Number(stream.withdrawn) / scale;
  const hourlyToken = rateToken * 3600;
  const remainingToken = Math.max(0, rateToken * remaining);
  const hourlyUsd = usdPrice == null ? null : hourlyToken * usdPrice;
  const remainingUsd = usdPrice == null ? null : remainingToken * usdPrice;

  return {
    symbol,
    rateToken,
    deposit,
    withdrawn,
    hourlyToken,
    remainingToken,
    hourlyUsd,
    remainingUsd,
  };
}

function formatStopTime(stopTime: bigint) {
  const seconds = Number(stopTime);
  if (!Number.isFinite(seconds) || seconds <= 0) return "-";
  return new Date(seconds * 1000).toLocaleString([], {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
