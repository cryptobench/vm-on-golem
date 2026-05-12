"use client";

import React from "react";
import { Spinner } from "../ui/Spinner";
import { cn } from "../ui/cn";

const STATUS_STYLES: Record<
  string,
  { label: string; className: string; dot: string }
> = {
  running: {
    label: "Running",
    className: "bg-success-soft text-success",
    dot: "bg-success",
  },
  creating: {
    label: "Creating",
    className: "bg-warning-soft text-warning",
    dot: "bg-warning",
  },
  stopped: {
    label: "Stopped",
    className: "bg-primary-soft text-primary",
    dot: "bg-primary",
  },
  suspended: {
    label: "Suspended",
    className: "bg-warning-soft text-warning",
    dot: "bg-warning",
  },
  terminated: {
    label: "Terminated",
    className: "bg-surface-muted text-text-muted",
    dot: "bg-text-muted",
  },
  deleted: {
    label: "Terminated",
    className: "bg-surface-muted text-text-muted",
    dot: "bg-text-muted",
  },
  error: {
    label: "Error",
    className: "bg-danger-soft text-danger",
    dot: "bg-danger",
  },
  failed: {
    label: "Error",
    className: "bg-danger-soft text-danger",
    dot: "bg-danger",
  },
};

export function RentalStatusPill({ status }: { status?: string | null }) {
  const normalized = String(status || "unknown").toLowerCase();
  const state = STATUS_STYLES[normalized] || {
    label: "Unknown",
    className: "bg-surface-muted text-text-secondary",
    dot: "bg-text-muted",
  };

  return (
    <span
      className={cn(
        "inline-flex h-6 items-center gap-1.5 rounded-full px-2 text-xs font-medium",
        state.className,
      )}
    >
      {normalized === "creating" ? (
        <Spinner className="h-3.5 w-3.5" />
      ) : (
        <span
          className={cn("h-1.5 w-1.5 rounded-full", state.dot)}
          aria-hidden
        />
      )}
      {state.label}
    </span>
  );
}
