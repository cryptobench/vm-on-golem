"use client";

import React from "react";
import { cn } from "./cn";

export function IconTile({
  children,
  tone = "primary",
  className,
}: {
  children: React.ReactNode;
  tone?: "primary" | "success" | "warning" | "danger" | "neutral";
  className?: string;
}) {
  const toneClass = {
    primary: "bg-primary-soft text-primary",
    success: "bg-success-soft text-success",
    warning: "bg-warning-soft text-warning",
    danger: "bg-danger-soft text-danger",
    neutral: "bg-surface-muted text-text-secondary",
  }[tone];

  return (
    <span className={cn("grid h-9 w-9 place-items-center rounded-lg", toneClass, className)}>
      {children}
    </span>
  );
}
