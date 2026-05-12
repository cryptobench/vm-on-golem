"use client";

import React from "react";
import { RiExternalLinkLine, RiSettings3Line } from "@remixicon/react";
import Link from "next/link";
import { CopyValue } from "../rentals/CopyValue";
import { cn } from "../ui/cn";
import { StreamRunway } from "./StreamRunway";
import { StreamStatusPill, VmActivity } from "./StreamStatusPill";
import { StreamTopUpControls } from "./StreamTopUpControls";
import {
  formatFiat,
  formatTokenAmount,
  hourlyTokenRate,
  remainingTokenBalance,
  streamStatus,
  type StreamRow,
} from "./streamModel";

type StreamView = "active" | "ended";

type StreamsTableProps = {
  active: StreamRow[];
  ended: StreamRow[];
  nowSec: number;
  showEnded: boolean;
  onShowEndedChange: (value: boolean) => void;
  busy: Record<string, boolean>;
  actionsDisabled: boolean;
  actionsDisabledReason?: string | null;
  onTopUp: (row: StreamRow, seconds: number) => void;
};

export function StreamsTable({
  active,
  ended,
  nowSec,
  showEnded,
  onShowEndedChange,
  busy,
  actionsDisabled,
  actionsDisabledReason,
  onTopUp,
}: StreamsTableProps) {
  const [view, setView] = React.useState<StreamView>("active");
  const rows = view === "ended" ? ended : active;

  React.useEffect(() => {
    if (view === "ended" && !ended.length) setView("active");
  }, [ended.length, view]);

  return (
    <section className="streams-table-shell overflow-hidden rounded-lg border border-border bg-surface shadow-soft">
      <div className="flex flex-col gap-4 border-b border-border sm:flex-row sm:items-center sm:justify-between">
        <div className="flex">
          <TabButton
            active={view === "active"}
            label={`Active streams (${active.length})`}
            onClick={() => setView("active")}
          />
          <TabButton
            active={view === "ended"}
            label={`Ended streams (${ended.length})`}
            onClick={() => setView("ended")}
          />
        </div>
        <div className="flex items-center gap-4 px-4 pb-4 sm:px-5 sm:pb-0">
          <label className="inline-flex items-center gap-3 text-sm font-medium text-text-secondary">
            <button
              className={cn(
                "relative h-6 w-11 rounded-full border border-border transition",
                showEnded ? "bg-primary" : "bg-border-strong",
              )}
              onClick={() => {
                const next = !showEnded;
                onShowEndedChange(next);
                setView(next ? "ended" : "active");
              }}
              role="switch"
              type="button"
              aria-checked={showEnded}
            >
              <span
                className={cn(
                  "absolute top-0.5 h-5 w-5 rounded-full bg-surface shadow-soft transition-transform",
                  showEnded ? "translate-x-5" : "translate-x-0.5",
                )}
                aria-hidden
              />
            </button>
            Show ended streams
          </label>
          <Link className="btn btn-secondary w-10 px-0" href="/settings" aria-label="Stream settings">
            <RiSettings3Line className="h-5 w-5" aria-hidden />
          </Link>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="table min-w-full">
          <thead className="bg-surface">
            <tr>
              {[
                "VM Name",
                "Stream ID",
                "Recipient / Provider ID",
                "Token",
                "Decimals",
                "Hourly Rate",
                "Remaining Time",
                "Remaining Balance",
                "Status",
                "Halted",
                "Actions",
              ].map((header) => (
                <th
                  className="th whitespace-nowrap py-4 normal-case tracking-normal"
                  key={header}
                >
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <StreamsTableRow
                key={`${row.r.vm_id}-${row.r.stream_id}`}
                row={row}
                nowSec={nowSec}
                busy={!!busy[String(row.r.stream_id)]}
                actionsDisabled={actionsDisabled}
                actionsDisabledReason={actionsDisabledReason}
                onTopUp={(seconds) => onTopUp(row, seconds)}
              />
            ))}
          </tbody>
        </table>
      </div>
      <div className="border-t border-border px-5 py-4 text-sm text-text-secondary">
        Showing {rows.length} of {active.length + ended.length} stream
        {active.length + ended.length === 1 ? "" : "s"}
      </div>
    </section>
  );
}

function TabButton({
  active,
  label,
  onClick,
}: {
  active: boolean;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      className={cn(
        "relative h-16 px-5 text-sm font-semibold transition",
        active ? "text-primary" : "text-text-secondary hover:text-text-primary",
      )}
      onClick={onClick}
      type="button"
    >
      {label}
      {active ? (
        <span className="absolute inset-x-0 bottom-0 h-0.5 rounded-md bg-primary" aria-hidden />
      ) : null}
    </button>
  );
}

function StreamsTableRow({
  row,
  nowSec,
  busy,
  actionsDisabled,
  actionsDisabledReason,
  onTopUp,
}: {
  row: StreamRow;
  nowSec: number;
  busy: boolean;
  actionsDisabled: boolean;
  actionsDisabledReason?: string | null;
  onTopUp: (seconds: number) => void;
}) {
  const status = streamStatus(row, nowSec);
  const tokenRate = hourlyTokenRate(row);
  const balance = remainingTokenBalance(row, nowSec);
  const hourlyUsd = row.usdPrice == null ? null : tokenRate * row.usdPrice;
  const balanceUsd = row.usdPrice == null ? null : balance * row.usdPrice;
  const terminal = row.chain.halted || status === "out-of-funds";

  return (
    <tr className="streams-table-row border-t border-border first:border-t-0">
      <td className="td whitespace-nowrap py-5">
        <Link
          className="font-semibold text-text-primary transition hover:text-primary"
          href={`/vm?id=${encodeURIComponent(row.r.vm_id)}`}
        >
          {row.r.name || row.r.vm_id}
        </Link>
        <div className="mt-2">
          <VmActivity status={row.r.status} />
        </div>
      </td>
      <td className="td whitespace-nowrap py-5">
        <CopyValue value={row.r.stream_id} />
      </td>
      <td className="td whitespace-nowrap py-5">
        <CopyValue value={row.chain.recipient || row.r.provider_id} />
      </td>
      <td className="td whitespace-nowrap py-5">
        <span className="inline-flex items-center gap-2 font-medium">
          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary text-xs font-semibold text-white">
            {(row.tokenSymbol || "T").slice(0, 1)}
          </span>
          {row.tokenSymbol || "TOKEN"}
        </span>
      </td>
      <td className="td whitespace-nowrap py-5 font-medium">{row.tokenDecimals || 18}</td>
      <td className="td whitespace-nowrap py-5">
        <div className="font-medium text-text-primary">
          {formatTokenAmount(tokenRate, row.tokenSymbol, 2)}
        </div>
        <div className="mt-1 text-xs text-text-secondary">
          {hourlyUsd == null ? "No fiat price" : `≈ ${formatFiat(hourlyUsd, 2)}`}
        </div>
      </td>
      <td className="td whitespace-nowrap py-5">
        <StreamRunway row={row} nowSec={nowSec} />
      </td>
      <td className="td whitespace-nowrap py-5">
        <div className="font-medium text-text-primary">
          {formatTokenAmount(balance, row.tokenSymbol, 2)}
        </div>
        <div className="mt-1 text-xs text-text-secondary">
          {balanceUsd == null ? "No fiat price" : `≈ ${formatFiat(balanceUsd, 2)}`}
        </div>
      </td>
      <td className="td whitespace-nowrap py-5">
        <StreamStatusPill status={status} />
      </td>
      <td className="td whitespace-nowrap py-5 font-medium">
        {row.chain.halted ? "Yes" : "No"}
      </td>
      <td className="td whitespace-nowrap py-5 text-right">
        {terminal ? (
          <Link
            className="inline-flex h-9 items-center gap-2 rounded-md px-3 text-sm font-medium text-primary transition hover:bg-surface-muted"
            href={`/vm?id=${encodeURIComponent(row.r.vm_id)}`}
          >
            Details
            <RiExternalLinkLine className="h-4 w-4" aria-hidden />
          </Link>
        ) : (
          <StreamTopUpControls
            busy={busy}
            disabled={actionsDisabled}
            disabledReason={actionsDisabledReason}
            onTopUp={onTopUp}
          />
        )}
      </td>
    </tr>
  );
}
