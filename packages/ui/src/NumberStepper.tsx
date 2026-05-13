"use client";

import React from "react";
import { RiAddLine, RiSubtractLine } from "@remixicon/react";
import { cn } from "./cn";

export function NumberStepper({
  label,
  value,
  min,
  max,
  disabled,
  hideLabel,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max?: number;
  disabled?: boolean;
  hideLabel?: boolean;
  onChange: (value: number) => void;
}) {
  const safeMax = max == null ? null : Math.max(min, Math.floor(max));
  const apply = (next: number) => {
    const bounded = Math.max(min, Math.floor(next));
    onChange(safeMax == null ? bounded : Math.min(bounded, safeMax));
  };

  return (
    <label className="grid gap-2">
      <span
        className={
          hideLabel ? "sr-only" : "text-sm font-medium text-text-secondary"
        }
      >
        {label}
      </span>
      <span className="grid h-10 grid-cols-[1fr_2.5rem_2.5rem] overflow-hidden rounded-md border border-border bg-surface">
        <input
          className="min-w-0 border-0 bg-transparent px-4 text-sm font-medium text-text-primary shadow-none focus:ring-0 disabled:text-text-muted"
          type="number"
          min={min}
          max={safeMax ?? undefined}
          value={value}
          onChange={(event) => apply(Number(event.target.value))}
          disabled={disabled}
        />
        <button
          type="button"
          className="grid place-items-center border-l border-border text-text-muted transition hover:bg-surface-muted hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-40"
          onClick={() => apply(value - 1)}
          disabled={disabled || value <= min}
          aria-label={`Decrease ${label}`}
          title={`Decrease ${label}`}
        >
          <RiSubtractLine className="h-4 w-4" aria-hidden />
        </button>
        <button
          type="button"
          className="grid place-items-center border-l border-border text-text-muted transition hover:bg-surface-muted hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-40"
          onClick={() => apply(value + 1)}
          disabled={disabled || (safeMax != null && value >= safeMax)}
          aria-label={`Increase ${label}`}
          title={`Increase ${label}`}
        >
          <RiAddLine className="h-4 w-4" aria-hidden />
        </button>
      </span>
    </label>
  );
}
