"use client";

import React from "react";
import {
  RiArrowDownSLine,
  RiRefreshLine,
  RiSettings3Line,
  RiMoneyDollarCircleLine,
} from "@remixicon/react";
import Link from "next/link";
import { Spinner } from "@golem/ui";
import type { DisplayCurrency } from "./streamModel";

type StreamsToolbarProps = {
  displayCurrency: DisplayCurrency;
  onDisplayCurrencyChange: (value: DisplayCurrency) => void;
  onRefresh: () => void;
  refreshing: boolean;
};

export function StreamsToolbar({
  displayCurrency,
  onDisplayCurrencyChange,
  onRefresh,
  refreshing,
}: StreamsToolbarProps) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-end">
      <label className="flex items-center gap-3 text-sm text-text-secondary">
        <span>Display in</span>
        <span className="relative">
          <RiMoneyDollarCircleLine
            className="pointer-events-none absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-text-secondary"
            aria-hidden
          />
          <select
            className="input h-10 min-w-40 appearance-none bg-surface pl-10 pr-8 text-sm font-medium text-text-primary"
            value={displayCurrency}
            onChange={(event) =>
              onDisplayCurrencyChange(event.target.value === "token" ? "token" : "fiat")
            }
          >
            <option value="fiat">USD (Fiat)</option>
            <option value="token">Token</option>
          </select>
          <RiArrowDownSLine
            className="pointer-events-none absolute right-3 top-1/2 h-5 w-5 -translate-y-1/2 text-text-secondary"
            aria-hidden
          />
        </span>
      </label>
      <button
        className="btn btn-secondary w-full gap-2 sm:w-10 sm:px-0"
        disabled={refreshing}
        onClick={onRefresh}
        type="button"
        aria-label="Refresh streams"
      >
        {refreshing ? (
          <Spinner className="h-4 w-4" />
        ) : (
          <RiRefreshLine className="h-5 w-5" aria-hidden />
        )}
        <span className="sm:sr-only">Refresh</span>
      </button>
      <Link
        className="btn btn-secondary w-full gap-2 sm:w-10 sm:px-0"
        href="/settings"
        aria-label="Stream settings"
      >
        <RiSettings3Line className="h-5 w-5" aria-hidden />
        <span className="sm:sr-only">Settings</span>
      </Link>
    </div>
  );
}
