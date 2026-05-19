"use client";

import React from "react";
import { cn } from "./cn";

export function ToggleSwitch({
  checked,
  onChange,
  label,
  disabled,
  className,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
  disabled?: boolean;
  className?: string;
}) {
  return (
    <button
      className={cn(
        "relative inline-flex h-6 w-11 shrink-0 rounded-full border border-border p-0 transition focus:outline-none focus:ring-2 focus:ring-primary disabled:cursor-not-allowed disabled:opacity-50",
        checked ? "bg-primary" : "bg-border-strong",
        className,
      )}
      onClick={() => onChange(!checked)}
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
    >
      <span
        className={cn(
          "pointer-events-none absolute left-0.5 top-1/2 h-5 w-5 -translate-y-1/2 rounded-full bg-surface shadow-soft transition-transform",
          checked ? "translate-x-5" : "translate-x-0",
        )}
        aria-hidden
      />
    </button>
  );
}
