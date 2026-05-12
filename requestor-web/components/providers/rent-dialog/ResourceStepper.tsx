"use client";

import React from "react";
import { RiAddLine, RiSubtractLine } from "@remixicon/react";
import { cn } from "../../ui/cn";

export function ResourceStepper({
  label,
  value,
  max,
  unit,
  step = 1,
  onChange,
}: {
  label: string;
  value: number;
  max: number;
  unit: string;
  step?: number;
  onChange: (value: number) => void;
}) {
  const min = 1;
  const safeMax = Math.max(min, Math.floor(max || min));
  const decrementDisabled = value <= min;
  const incrementDisabled = value >= safeMax;

  const update = (next: number) => {
    onChange(Math.min(Math.max(Math.floor(next), min), safeMax));
  };

  return (
    <div>
      <label className="label">{label}</label>
      <div className="mt-2 grid h-10 grid-cols-[2.5rem_minmax(3rem,1fr)_2.5rem] overflow-hidden rounded-md border border-border bg-surface">
        <StepButton
          label={`Decrease ${label}`}
          disabled={decrementDisabled}
          onClick={() => update(value - step)}
        >
          <RiSubtractLine className="h-4 w-4" aria-hidden />
        </StepButton>
        <input
          className="min-w-0 border-0 bg-surface px-2 text-center text-sm font-semibold text-text-primary focus:ring-0"
          aria-label={`${label} ${unit}`}
          type="number"
          min={min}
          max={safeMax}
          value={value}
          onChange={(event) => update(Number(event.target.value))}
        />
        <StepButton
          label={`Increase ${label}`}
          disabled={incrementDisabled}
          onClick={() => update(value + step)}
        >
          <RiAddLine className="h-4 w-4" aria-hidden />
        </StepButton>
      </div>
    </div>
  );
}

function StepButton({
  label,
  disabled,
  onClick,
  children,
}: {
  label: string;
  disabled: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      className={cn(
        "flex h-10 items-center justify-center text-text-secondary transition hover:bg-surface-muted hover:text-text-primary",
        disabled && "cursor-not-allowed opacity-40 hover:bg-surface hover:text-text-secondary",
      )}
      disabled={disabled}
      onClick={onClick}
    >
      {children}
    </button>
  );
}
