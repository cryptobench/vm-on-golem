"use client";

import React from "react";
import {
  RiAddLine,
  RiFileCopyLine,
  RiInformationLine,
  RiSubtractLine,
} from "@remixicon/react";
import { cn } from "../../ui/cn";

type DetailPanelProps = {
  children: React.ReactNode;
  className?: string;
};

export function DetailPanel({ children, className }: DetailPanelProps) {
  return (
    <section className={cn("vm-panel card", className)}>
      <div className="card-body">{children}</div>
    </section>
  );
}

export function PanelTitle({
  title,
  hint,
  trailing,
}: {
  title: string;
  hint?: string;
  trailing?: React.ReactNode;
}) {
  return (
    <div className="flex min-h-6 items-center justify-between gap-3">
      <div className="flex min-w-0 items-center gap-2">
        <h3 className="truncate text-base font-semibold text-text-primary">
          {title}
        </h3>
        {hint && (
          <span title={hint}>
            <RiInformationLine
              className="h-4 w-4 text-text-muted"
              aria-label={hint}
            />
          </span>
        )}
      </div>
      {trailing}
    </div>
  );
}

export function InfoField({
  label,
  children,
  className,
}: {
  label: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("min-w-0", className)}>
      <div className="text-xs font-medium text-text-muted">{label}</div>
      <div className="mt-2 min-w-0 text-sm font-medium text-text-primary">
        {children}
      </div>
    </div>
  );
}

export function CopyInline({
  value,
  display,
  onCopy,
  className,
}: {
  value?: string | number | null;
  display?: React.ReactNode;
  onCopy: (value: string) => void;
  className?: string;
}) {
  const copyValue = value == null ? "" : String(value);

  return (
    <span className={cn("inline-flex min-w-0 items-center gap-2", className)}>
      <span
        className="min-w-0 truncate font-mono"
        title={copyValue || undefined}
      >
        {display ?? (copyValue || "-")}
      </span>
      <button
        type="button"
        className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-text-muted transition hover:bg-surface-muted hover:text-text-primary focus:outline-none focus:ring-2 focus:ring-primary"
        onClick={() => copyValue && onCopy(copyValue)}
        disabled={!copyValue}
        aria-label="Copy value"
        title="Copy"
      >
        <RiFileCopyLine className="h-4 w-4" aria-hidden />
      </button>
    </span>
  );
}

export function IconButton({
  label,
  children,
  className,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      className={cn(
        "inline-flex h-10 w-10 items-center justify-center rounded-md bg-surface text-text-secondary ring-1 ring-inset ring-border transition hover:bg-surface-muted hover:text-text-primary focus:outline-none focus:ring-2 focus:ring-primary disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      aria-label={label}
      title={label}
      {...props}
    >
      {children}
    </button>
  );
}

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

export function shortAddress(value?: string | number | null) {
  if (value == null) return "-";
  const text = String(value);
  if (text.length <= 13) return text;
  return `${text.slice(0, 6)}...${text.slice(-4)}`;
}
