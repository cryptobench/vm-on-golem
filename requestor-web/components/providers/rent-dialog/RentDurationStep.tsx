"use client";

import React from "react";
import { RiInformationLine } from "@remixicon/react";
import { Input, SelectableCard } from "@golem/ui";
import { DURATION_OPTIONS, type RentDurationPreset } from "./constants";
import { durationTotal, formatUsd } from "./formatting";
import { RentStepSection } from "./RentStepSection";

export function RentDurationStep({
  preset,
  customInput,
  customSeconds,
  monthlyUsd,
  onPresetChange,
  onCustomInputChange,
}: {
  preset: RentDurationPreset;
  customInput: string;
  customSeconds: number;
  monthlyUsd?: number;
  onPresetChange: (preset: RentDurationPreset) => void;
  onCustomInputChange: (value: string) => void;
}) {
  return (
    <RentStepSection
      title="Choose your rental duration"
      description="Select a duration or enter a custom one."
    >
      <div className="mt-6 grid gap-3 sm:grid-cols-4">
        {DURATION_OPTIONS.map((option) => (
          <SelectableCard
            key={option.preset}
            selected={preset === option.preset}
            onClick={() => onPresetChange(option.preset)}
          >
            <span className="font-semibold text-text-primary">
              {option.label}
            </span>
            <span className="mt-5 font-semibold text-text-primary">
              {formatUsd(durationTotal(monthlyUsd, option.seconds) || 0)}
            </span>
            <span className="mt-1 text-sm text-text-secondary">total</span>
          </SelectableCard>
        ))}
      </div>
      <label className="label mt-7">Custom duration</label>
      <div className="relative mt-2 max-w-2xl">
        <Input
          inputClassName="h-10 pr-10"
          placeholder="e.g. 2d 12h or 45h 30m"
          value={customInput}
          onChange={(event) => {
            onPresetChange("custom");
            onCustomInputChange(event.target.value);
          }}
        />
        <RiInformationLine
          className="absolute right-3 top-3 h-4 w-4 text-text-secondary"
          aria-hidden
        />
      </div>
      <div className="mt-3 text-sm text-text-secondary">
        Enter a duration in days (d) and hours (h). Minimum is 1 hour.
      </div>
      {preset === "custom" && customInput.trim() && customSeconds <= 0 ? (
        <div className="mt-2 text-sm text-danger">Enter a valid duration.</div>
      ) : null}
    </RentStepSection>
  );
}
