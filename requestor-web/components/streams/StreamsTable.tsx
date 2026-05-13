"use client";

import React from "react";
import {
  RiCloseLine,
  RiExternalLinkLine,
  RiInformationLine,
  RiSettings3Line,
  RiTimeLine,
} from "@remixicon/react";
import Link from "next/link";
import { CopyValue } from "../rentals/CopyValue";
import { humanDuration } from "../../lib/streams";
import { parseHumanDuration } from "../../lib/time";
import { vmDetailsHref } from "../../lib/routes";
import { Button } from "../ui/Button";
import { Modal } from "../ui/Modal";
import { cn } from "../ui/cn";
import { StreamRunway } from "./StreamRunway";
import { VmActivity } from "./StreamStatusPill";
import {
  type DisplayCurrency,
  formatFiat,
  hourlyTokenRate,
  remainingTokenBalance,
  remainingSeconds,
  spentTokenBalance,
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
  displayCurrency: DisplayCurrency;
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
  displayCurrency,
  onTopUp,
}: StreamsTableProps) {
  const [view, setView] = React.useState<StreamView>(
    showEnded && ended.length ? "ended" : "active",
  );
  const previousShowEnded = React.useRef(showEnded);
  const rows = React.useMemo(
    () => sortRowsByImportance(view === "ended" ? ended : active, nowSec),
    [active, ended, nowSec, view],
  );

  React.useEffect(() => {
    const wasShowingEnded = previousShowEnded.current;
    previousShowEnded.current = showEnded;

    if (!showEnded) {
      setView("active");
      return;
    }

    if (!wasShowingEnded && ended.length) {
      setView("ended");
    }
  }, [ended.length, showEnded]);

  React.useEffect(() => {
    if (view === "ended" && (!showEnded || !ended.length)) {
      setView("active");
    }
  }, [ended.length, showEnded, view]);

  const toggleShowEnded = () => {
    const next = !showEnded;
    onShowEndedChange(next);
    setView(next && ended.length ? "ended" : "active");
  };

  return (
    <section className="streams-table-shell overflow-hidden rounded-lg border border-border bg-surface shadow-soft">
      <div className="flex flex-col gap-4 border-b border-border sm:flex-row sm:items-center sm:justify-between">
        <div className="flex">
          <TabButton
            active={view === "active"}
            label={`Active streams (${active.length})`}
            onClick={() => setView("active")}
          />
          {showEnded ? (
            <TabButton
              active={view === "ended"}
              label={`Ended streams (${ended.length})`}
              onClick={() => setView("ended")}
            />
          ) : null}
        </div>
        <div className="flex items-center gap-4 px-4 pb-4 sm:px-5 sm:pb-0">
          <button
            className="inline-flex h-10 select-none items-center gap-3 text-sm font-medium text-text-secondary transition hover:text-text-primary focus:outline-none focus:ring-2 focus:ring-primary"
            onClick={toggleShowEnded}
            role="switch"
            type="button"
            aria-checked={showEnded}
          >
            <span
              className={cn(
                "relative h-6 w-11 shrink-0 rounded-full border border-border transition",
                showEnded ? "bg-primary" : "bg-border-strong",
              )}
              aria-hidden
            >
              <span
                className={cn(
                  "absolute left-0 top-0.5 h-5 w-5 rounded-full bg-surface shadow-soft transition-transform",
                  showEnded ? "translate-x-5" : "translate-x-0.5",
                )}
                aria-hidden
              />
            </span>
            <span>Show ended streams</span>
          </button>
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
                "VM",
                "Remaining Time",
                "Spent So Far",
                "Remaining Balance",
                "Hourly Rate",
                "Token",
                "Provider",
                "Stream ID",
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
                displayCurrency={displayCurrency}
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
  displayCurrency,
  onTopUp,
}: {
  row: StreamRow;
  nowSec: number;
  busy: boolean;
  actionsDisabled: boolean;
  actionsDisabledReason?: string | null;
  displayCurrency: DisplayCurrency;
  onTopUp: (seconds: number) => void;
}) {
  const [topUpOpen, setTopUpOpen] = React.useState(false);
  const status = streamStatus(row, nowSec);
  const tokenRate = hourlyTokenRate(row);
  const spent = spentTokenBalance(row, nowSec);
  const balance = remainingTokenBalance(row, nowSec);
  const hourlyUsd = row.usdPrice == null ? null : tokenRate * row.usdPrice;
  const terminal = row.chain.halted || status === "out-of-funds";

  return (
    <tr className="streams-table-row border-t border-border first:border-t-0">
      <td className="td whitespace-nowrap py-5">
        <Link
          className="font-semibold text-text-primary transition hover:text-primary"
          href={vmDetailsHref(row.r.vm_id)}
        >
          {row.r.name || row.r.vm_id}
        </Link>
        <div className="mt-2">
          <VmActivity status={row.r.status} />
        </div>
      </td>
      <td className="td whitespace-nowrap py-5">
        <StreamRunway row={row} nowSec={nowSec} />
      </td>
      <td className="td whitespace-nowrap py-5">
        <CurrencyCell
          amount={spent}
          displayCurrency={displayCurrency}
          row={row}
        />
      </td>
      <td className="td whitespace-nowrap py-5">
        <CurrencyCell
          amount={balance}
          displayCurrency={displayCurrency}
          row={row}
        />
      </td>
      <td className="td whitespace-nowrap py-5">
        <CurrencyCell
          amount={tokenRate}
          displayCurrency={displayCurrency}
          row={row}
          fiatAmount={hourlyUsd}
          tokenLabelSuffix="/h"
        />
      </td>
      <td className="td whitespace-nowrap py-5">
        <span className="inline-flex items-center gap-2 font-medium">
          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary text-xs font-semibold text-white">
            {(row.tokenSymbol || "T").slice(0, 1)}
          </span>
          {row.tokenSymbol || "TOKEN"}
        </span>
      </td>
      <td className="td whitespace-nowrap py-5">
        <CopyValue value={row.chain.recipient || row.r.provider_id} />
      </td>
      <td className="td whitespace-nowrap py-5">
        <CopyValue value={row.r.stream_id} />
      </td>
      <td className="td whitespace-nowrap py-5 text-right">
        {terminal ? (
          <Link
            className="inline-flex h-9 items-center gap-2 rounded-md px-3 text-sm font-medium text-primary transition hover:bg-surface-muted"
            href={vmDetailsHref(row.r.vm_id)}
          >
            Details
            <RiExternalLinkLine className="h-4 w-4" aria-hidden />
          </Link>
        ) : (
          <>
            <Button
              variant="secondary"
              className="px-3 text-primary ring-border"
              disabled={busy || actionsDisabled}
              title={actionsDisabledReason || undefined}
              onClick={() => setTopUpOpen(true)}
            >
              Top up
            </Button>
            <StreamTopUpModal
              open={topUpOpen}
              row={row}
              busy={busy}
              disabled={actionsDisabled}
              disabledReason={actionsDisabledReason}
              onClose={() => setTopUpOpen(false)}
              onTopUp={(seconds) => onTopUp(seconds)}
            />
          </>
        )}
      </td>
    </tr>
  );
}

const TOP_UP_PRESETS = [
  { label: "30 min", seconds: 1800 },
  { label: "1 hour", seconds: 3600 },
  { label: "2 hours", seconds: 7200 },
  { label: "6 hours", seconds: 21600 },
];

function StreamTopUpModal({
  open,
  row,
  busy,
  disabled,
  disabledReason,
  onClose,
  onTopUp,
}: {
  open: boolean;
  row: StreamRow;
  busy: boolean;
  disabled: boolean;
  disabledReason?: string | null;
  onClose: () => void;
  onTopUp: (seconds: number) => void;
}) {
  const [selectedSeconds, setSelectedSeconds] = React.useState(3600);
  const [custom, setCustom] = React.useState("");
  const customSeconds = parseHumanDuration(custom);
  const usingCustom = custom.trim().length > 0;
  const topUpSeconds = usingCustom ? customSeconds : selectedSeconds;
  const blocked = disabled || (usingCustom && customSeconds <= 0);
  const buttonTitle =
    disabledReason ||
    (usingCustom && customSeconds <= 0 ? "Enter a valid duration." : undefined);
  const tokenRate = hourlyTokenRate(row);
  const topUpToken = (tokenRate / 3600) * Math.max(0, topUpSeconds);
  const topUpFiat = row.usdPrice == null ? null : topUpToken * row.usdPrice;

  React.useEffect(() => {
    if (!open) {
      setSelectedSeconds(3600);
      setCustom("");
    }
  }, [open]);

  const submit = () => {
    if (blocked || busy || topUpSeconds <= 0) return;
    onTopUp(topUpSeconds);
  };

  return (
    <Modal open={open} onClose={busy ? () => undefined : onClose} size="lg">
      <div className="p-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-text-primary">
              Top up stream
            </h2>
            <p className="mt-3 text-sm leading-5 text-text-secondary">
              Select how much runway to add to {row.r.name || row.r.vm_id}.
            </p>
          </div>
          <button
            type="button"
            className="inline-flex h-8 w-8 items-center justify-center rounded-md text-text-muted transition hover:bg-surface-muted hover:text-text-primary"
            onClick={onClose}
            disabled={busy}
            aria-label="Close top-up dialog"
          >
            <RiCloseLine className="h-5 w-5" aria-hidden />
          </button>
        </div>

        <div className="mt-6 grid gap-2 sm:grid-cols-4">
          {TOP_UP_PRESETS.map((preset) => (
            <button
              key={preset.seconds}
              type="button"
              className={cn(
                "flex min-h-16 flex-col items-center justify-center rounded-md border border-border bg-surface px-3 py-2 text-center transition hover:border-border-strong hover:bg-surface-muted",
                !usingCustom &&
                  selectedSeconds === preset.seconds &&
                  "border-primary bg-primary-soft ring-1 ring-primary",
              )}
              onClick={() => {
                setCustom("");
                setSelectedSeconds(preset.seconds);
              }}
              disabled={busy}
            >
              <span className="text-sm font-semibold text-text-primary">
                {preset.label}
              </span>
              <span className="mt-1 text-xs text-text-secondary">
                {humanDuration(preset.seconds)}
              </span>
            </button>
          ))}
        </div>

        <label className="label mt-5">Custom duration</label>
        <div className="relative mt-2">
          <input
            className="input h-10 pr-10"
            placeholder="45m, 1h, 2d"
            value={custom}
            onChange={(event) => setCustom(event.target.value)}
            disabled={busy}
          />
          <RiTimeLine
            className="absolute right-3 top-3 h-4 w-4 text-text-muted"
            aria-hidden
          />
        </div>
        {usingCustom && customSeconds <= 0 ? (
          <div className="mt-2 text-sm text-danger">Enter a valid duration.</div>
        ) : null}

        <div className="mt-5 flex items-center gap-2 rounded-md bg-surface-muted px-3 py-2 text-sm text-text-secondary">
          <RiInformationLine
            className="h-4 w-4 shrink-0 text-primary"
            aria-hidden
          />
          <span>
            Adds {humanDuration(Math.max(0, topUpSeconds))} for about{" "}
            {formatTokenValue(topUpToken, row.tokenSymbol)}
            {topUpFiat == null ? "" : ` (${formatFiat(topUpFiat, 2)})`}.
          </span>
        </div>

        {disabledReason ? (
          <div className="mt-4 rounded-md border border-warning bg-warning-soft p-3 text-sm text-text-primary">
            {disabledReason}
          </div>
        ) : null}

        <div className="mt-5 flex justify-end gap-3">
          <Button
            variant="secondary"
            className="px-6"
            onClick={onClose}
            disabled={busy}
          >
            Cancel
          </Button>
          <Button
            variant="primary"
            className="min-w-40 px-6"
            onClick={submit}
            disabled={blocked}
            busy={busy}
            title={buttonTitle}
          >
            {busy ? "Sending" : "Top up"}
          </Button>
        </div>
      </div>
    </Modal>
  );
}

function CurrencyCell({
  amount,
  displayCurrency,
  row,
  fiatAmount,
  tokenLabelSuffix = "",
}: {
  amount: number;
  displayCurrency: DisplayCurrency;
  row: StreamRow;
  fiatAmount?: number | null;
  tokenLabelSuffix?: string;
}) {
  const fiat = fiatAmount === undefined
    ? row.usdPrice == null
      ? null
      : amount * row.usdPrice
    : fiatAmount;
  const tokenValue = `${formatTokenValue(amount, row.tokenSymbol)}${tokenLabelSuffix}`;

  return (
    <div>
      <div className="font-medium text-text-primary">
        {displayCurrency === "fiat" && fiat != null
          ? `${formatFiat(fiat, 2)}${tokenLabelSuffix}`
          : tokenValue}
      </div>
      <div className="mt-1 text-xs text-text-secondary">
        {displayCurrency === "fiat" && fiat != null
          ? tokenValue
          : fiat == null
            ? "No fiat price"
            : `${formatFiat(fiat, 2)}${tokenLabelSuffix}`}
      </div>
    </div>
  );
}

function formatTokenValue(value: number, symbol: string) {
  return `${value.toFixed(4)} ${symbol || "TOKEN"}`;
}

function sortRowsByImportance(rows: StreamRow[], nowSec: number) {
  const statusRank: Record<ReturnType<typeof streamStatus>, number> = {
    "needs-top-up": 0,
    "out-of-funds": 1,
    halted: 2,
    active: 3,
  };

  return [...rows].sort((left, right) => {
    const leftStatus = streamStatus(left, nowSec);
    const rightStatus = streamStatus(right, nowSec);
    const statusDelta = statusRank[leftStatus] - statusRank[rightStatus];
    if (statusDelta !== 0) return statusDelta;

    const remainingDelta =
      remainingSeconds(left, nowSec) - remainingSeconds(right, nowSec);
    if (remainingDelta !== 0) return remainingDelta;

    return (left.r.name || left.r.vm_id).localeCompare(
      right.r.name || right.r.vm_id,
    );
  });
}
