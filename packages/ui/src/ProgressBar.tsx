"use client";

import React from "react";
import { cn } from "./cn";

export function ProgressBar({
  value,
  tone = "primary",
  className,
}: {
  value: number;
  tone?: "primary" | "success" | "warning" | "danger" | "neutral";
  className?: string;
}) {
  const bounded = Math.max(0, Math.min(100, value));
  const toneClass = {
    primary: "bg-primary",
    success: "bg-success",
    warning: "bg-warning",
    danger: "bg-danger",
    neutral: "bg-text-muted",
  }[tone];

  return (
    <div
      className={cn("h-2 overflow-hidden rounded-full bg-surface-muted", className)}
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={bounded}
    >
      <div className={cn("h-full rounded-full", toneClass)} style={{ width: `${bounded}%` }} />
    </div>
  );
}
