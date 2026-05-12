"use client";

import React from "react";
import { Spinner } from "../ui/Spinner";
import { cn } from "../ui/cn";
import { deriveVmLifecycle } from "../../lib/vmLifecycle";

export function RentalStatusPill({ status }: { status?: string | null }) {
  const lifecycle = deriveVmLifecycle({ status });
  const className = {
    success: "bg-success-soft text-success",
    warning: "bg-warning-soft text-warning",
    danger: "bg-danger-soft text-danger",
    neutral: "bg-surface-muted text-text-secondary",
    primary: "bg-primary-soft text-primary",
  }[lifecycle.tone];

  return (
    <span
      className={cn(
        "inline-flex h-6 items-center gap-1.5 rounded-full px-2 text-xs font-medium",
        className,
      )}
    >
      {lifecycle.transitioning ? (
        <Spinner className="h-3.5 w-3.5" />
      ) : (
        <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden />
      )}
      {lifecycle.label}
    </span>
  );
}
