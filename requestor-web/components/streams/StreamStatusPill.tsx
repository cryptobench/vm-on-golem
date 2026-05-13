"use client";

import React from "react";
import { cn } from "@golem/ui";
import type { StreamStatusKind } from "./streamModel";

const STATUS_LABELS: Record<StreamStatusKind, string> = {
  active: "Active",
  "needs-top-up": "Needs top-up",
  "out-of-funds": "Out of funds",
  halted: "Halted",
};

const STATUS_STYLES: Record<StreamStatusKind, string> = {
  active: "bg-success-soft text-success",
  "needs-top-up": "bg-warning-soft text-warning",
  "out-of-funds": "bg-danger-soft text-danger",
  halted: "bg-danger-soft text-danger",
};

export function StreamStatusPill({ status }: { status: StreamStatusKind }) {
  return (
    <span
      className={cn(
        "inline-flex h-7 items-center rounded-md px-3 text-xs font-medium",
        STATUS_STYLES[status],
      )}
    >
      {STATUS_LABELS[status]}
    </span>
  );
}

export function VmActivity({ status }: { status?: string | null }) {
  const normalized = String(status || "").toLowerCase();
  const active = normalized === "running";
  const starting = normalized === "starting" || normalized === "provisioning";

  return (
    <span className="inline-flex items-center gap-2 text-xs text-text-secondary">
      <span
        className={cn(
          "h-2 w-2 rounded-full",
          active || starting ? "streams-live-dot bg-success" : "bg-text-muted",
        )}
        aria-hidden
      />
      {formatStatus(status)}
    </span>
  );
}

function formatStatus(status?: string | null) {
  if (!status) return "Unknown";
  return status
    .split(/[_\s-]+/)
    .filter(Boolean)
    .map((part) => part.slice(0, 1).toUpperCase() + part.slice(1).toLowerCase())
    .join(" ");
}
