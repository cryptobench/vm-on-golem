"use client";

import React from "react";
import Link from "next/link";
import {
  RiInformationLine,
  RiRefreshLine,
  RiSettings3Line,
} from "@remixicon/react";
import { Input, ToggleSwitch } from "@golem/ui";

type RentalsToolbarProps = {
  query: string;
  onQueryChange: (value: string) => void;
  showTerminated: boolean;
  onShowTerminatedChange: (value: boolean) => void;
  onRefresh: () => void;
};

export function RentalsToolbar({
  query,
  onQueryChange,
  showTerminated,
  onShowTerminatedChange,
  onRefresh,
}: RentalsToolbarProps) {
  return (
    <div className="flex w-full flex-col gap-3 lg:max-w-4xl lg:flex-row lg:items-center lg:justify-end">
      <div className="hidden items-center gap-2 text-sm text-text-secondary lg:flex">
        <span className="h-2 w-2 rounded-full bg-success" aria-hidden />
        Auto-updating
        <button
          className="inline-flex h-8 w-8 items-center justify-center rounded-md text-text-secondary transition hover:bg-surface-muted hover:text-primary focus:outline-none focus:ring-2 focus:ring-primary"
          onClick={onRefresh}
          type="button"
          aria-label="Refresh VM list"
        >
          <RiRefreshLine className="h-4 w-4" aria-hidden />
        </button>
      </div>

      <label className="relative min-w-0 flex-1 lg:max-w-md">
        <span className="sr-only">Search VMs</span>
        <Input
          type="search"
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="Search VMs by name or ID..."
        />
      </label>

      <div className="flex items-center justify-between gap-3 lg:justify-end">
        <div className="inline-flex h-10 items-center gap-3 text-sm text-text-secondary">
          <ToggleSwitch
            checked={showTerminated}
            label="Show terminated VMs"
            onChange={onShowTerminatedChange}
          />
          <span>Show terminated VMs</span>
          <RiInformationLine
            className="h-5 w-5 text-text-secondary"
            aria-hidden
          />
        </div>
        <Link
          className="btn btn-secondary w-10 px-0"
          href="/settings"
          aria-label="Open project settings"
        >
          <RiSettings3Line className="h-5 w-5" aria-hidden />
        </Link>
      </div>
    </div>
  );
}
