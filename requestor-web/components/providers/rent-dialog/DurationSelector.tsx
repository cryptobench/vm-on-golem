"use client";

import React from "react";
import { RiTimeLine } from "@remixicon/react";
import { humanDuration } from "../../../lib/streams";
import { SelectableCard } from "@golem/ui";
import type { DurationOption, DurationPreset } from "./types";

export const DURATION_OPTIONS: DurationOption[] = [
  { preset: "1w", label: "1 week", seconds: 7 * 24 * 3600 },
  { preset: "2w", label: "2 weeks", seconds: 14 * 24 * 3600 },
  { preset: "30d", label: "30 days", seconds: 30 * 24 * 3600 },
];

export function DurationSelector({
  preset,
  customInput,
  customSeconds,
  onPresetChange,
  onCustomInputChange,
}: {
  preset: DurationPreset;
  customInput: string;
  customSeconds: number;
  onPresetChange: (preset: DurationPreset) => void;
  onCustomInputChange: (value: string) => void;
}) {
  return (
    <div>
      <div className="grid gap-2 sm:grid-cols-4">
        {DURATION_OPTIONS.map((option) => (
          <DurationButton
            key={option.preset}
            active={preset === option.preset}
            label={option.label}
            detail={`approx. ${humanDuration(option.seconds)}`}
            onClick={() => onPresetChange(option.preset)}
          />
        ))}
        <DurationButton
          active={preset === "custom"}
          label="Custom"
          detail="Set duration"
          onClick={() => onPresetChange("custom")}
        />
      </div>
      <label className="label mt-5">Custom duration</label>
      <div className="relative mt-2">
        <input
          className="input h-10 pr-10"
          placeholder="e.g. 45h 30m or 2d 12h"
          value={customInput}
          onChange={(event) => {
            onPresetChange("custom");
            onCustomInputChange(event.target.value);
          }}
        />
        <RiTimeLine className="absolute right-3 top-3 h-4 w-4 text-text-muted" aria-hidden />
      </div>
      {preset === "custom" && customInput.trim() && customSeconds <= 0 ? (
        <div className="mt-2 text-sm text-danger">Enter a valid duration.</div>
      ) : null}
    </div>
  );
}

function DurationButton({
  active,
  label,
  detail,
  onClick,
}: {
  active: boolean;
  label: string;
  detail: string;
  onClick: () => void;
}) {
  return (
    <SelectableCard selected={active} onClick={onClick} className="min-h-16 px-3 py-2">
      <span className="text-sm font-semibold text-text-primary">{label}</span>
      <span className="mt-1 text-xs text-text-secondary">{detail}</span>
    </SelectableCard>
  );
}
