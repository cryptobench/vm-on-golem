"use client";
import React from "react";
import { Spinner } from "./Spinner";
import { cn } from "./cn";

export type StatusBadgeTone =
  | "success"
  | "warning"
  | "danger"
  | "neutral"
  | "primary";

export function StatusBadge({
  label,
  tone = "neutral",
  busy = false,
  className,
}: {
  label: React.ReactNode;
  tone?: StatusBadgeTone;
  busy?: boolean;
  className?: string;
}) {
  const classes = {
    success: "bg-success-soft text-success",
    warning: "bg-warning-soft text-warning",
    danger: "bg-danger-soft text-danger",
    neutral: "bg-surface-muted text-text-secondary",
    primary: "bg-primary-soft text-primary",
  }[tone];

  return (
    <span
      className={cn(
        "inline-flex h-6 items-center gap-1.5 rounded-full px-2 text-xs font-medium",
        classes,
        className,
      )}
    >
      {busy ? (
        <Spinner className="h-3.5 w-3.5" />
      ) : (
        <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden />
      )}
      {label}
    </span>
  );
}
