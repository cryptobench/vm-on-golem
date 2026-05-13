"use client";

import React from "react";
import { cn } from "./cn";

type AlertTone = "danger" | "warning" | "info" | "success";

const TONE_CLASS: Record<AlertTone, string> = {
  danger: "border-danger bg-danger-soft text-danger",
  warning: "border-warning bg-warning-soft text-text-primary",
  info: "border-border bg-primary-soft text-text-secondary",
  success: "border-success bg-success-soft text-success",
};

export function Alert({
  tone = "info",
  children,
  className,
}: {
  tone?: AlertTone;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "rounded-md border px-4 py-3 text-sm",
        TONE_CLASS[tone],
        className,
      )}
    >
      {children}
    </div>
  );
}
