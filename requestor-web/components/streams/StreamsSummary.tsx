"use client";

import React from "react";
import {
  RiRadioButtonLine,
  RiTimeLine,
  RiWallet3Line,
} from "@remixicon/react";
import { cn } from "../ui/cn";
import {
  fiatTotal,
  formatFiat,
  formatTokenAmount,
  hourlyTokenRate,
  remainingTokenBalance,
  tokenTotals,
  type DisplayCurrency,
  type StreamRow,
} from "./streamModel";

type StreamsSummaryProps = {
  active: StreamRow[];
  ended: StreamRow[];
  displayCurrency: DisplayCurrency;
  nowSec: number;
  onShowEnded: () => void;
};

export function StreamsSummary({
  active,
  ended,
  displayCurrency,
  nowSec,
  onShowEnded,
}: StreamsSummaryProps) {
  const hourlyTokens = tokenTotals(active, hourlyTokenRate);
  const remainingTokens = tokenTotals(active, (row) => remainingTokenBalance(row, nowSec));
  const hourlyUsd = fiatTotal(active, hourlyTokenRate);
  const remainingUsd = fiatTotal(active, (row) => remainingTokenBalance(row, nowSec));

  return (
    <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      <SummaryCard
        label="Active streams"
        value={String(active.length)}
        detail={active.length ? "Live" : "No active streams"}
        visual={<PulseVisual />}
      />
      <SummaryCard
        label="Ended streams"
        value={String(ended.length)}
        detail={
          ended.length ? (
            <button
              className="font-medium text-primary transition hover:text-primary-hover"
              onClick={onShowEnded}
              type="button"
            >
              View history
            </button>
          ) : (
            "No ended streams"
          )
        }
        visual={<RiTimeLine className="h-12 w-12 text-brand-300" aria-hidden />}
      />
      <SummaryCard
        label="Hourly spend (total)"
        value={
          displayCurrency === "fiat"
            ? formatFiat(hourlyUsd, 2)
            : formatTokenList(hourlyTokens, " / hour")
        }
        detail={
          displayCurrency === "fiat"
            ? approxTokenList(hourlyTokens, " / hour")
            : formatFiat(hourlyUsd, 2) + " / hour"
        }
        visual={<Sparkline />}
      />
      <SummaryCard
        label="Remaining balance (total)"
        value={
          displayCurrency === "fiat"
            ? formatFiat(remainingUsd, 2)
            : formatTokenList(remainingTokens)
        }
        detail={
          displayCurrency === "fiat"
            ? approxTokenList(remainingTokens)
            : formatFiat(remainingUsd, 2)
        }
        visual={<RiWallet3Line className="h-12 w-12 text-brand-400" aria-hidden />}
      />
    </section>
  );
}

function SummaryCard({
  label,
  value,
  detail,
  visual,
}: {
  label: string;
  value: React.ReactNode;
  detail: React.ReactNode;
  visual: React.ReactNode;
}) {
  return (
    <article className="streams-summary-card rounded-lg border border-border bg-surface p-5 shadow-soft">
      <div className="flex items-center justify-between gap-4">
        <div className="min-w-0">
          <div className="text-sm font-medium text-text-secondary">{label}</div>
          <div className="mt-3 truncate text-2xl font-semibold text-text-primary">{value}</div>
          <div className="mt-3 text-sm text-text-secondary">{detail}</div>
        </div>
        <div className="shrink-0 text-primary">{visual}</div>
      </div>
    </article>
  );
}

function PulseVisual() {
  return (
    <span className="relative flex h-12 w-12 items-center justify-center text-success" aria-hidden>
      <span className="absolute h-9 w-9 rounded-full border-2 border-current opacity-50 streams-pulse-ring" />
      <RiRadioButtonLine className="h-8 w-8" />
    </span>
  );
}

function Sparkline() {
  return (
    <svg
      className="h-12 w-16 text-brand-400"
      viewBox="0 0 72 48"
      fill="none"
      aria-hidden
    >
      <path
        d="M3 36 C10 25 15 32 20 21 C25 10 28 34 34 18 C41 0 44 39 51 19 C57 4 59 29 69 12"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="3"
      />
    </svg>
  );
}

function formatTokenList(totals: Array<{ symbol: string; value: number }>, suffix = "") {
  if (!totals.length) return "0";
  return totals
    .map((item) => `${formatTokenAmount(item.value, item.symbol, 2)}${suffix}`)
    .join(" + ");
}

function approxTokenList(totals: Array<{ symbol: string; value: number }>, suffix = "") {
  return cn("≈", formatTokenList(totals, suffix));
}
