import React from "react";
import { IconTile } from "@golem/ui";
import { ResourceLimit } from "./SettingsShared";
import type { ResourceField } from "./settingsConstants";

export function ResourceControl({
  field,
  value,
  min,
  max,
  allocated,
  showValueInput = true,
  showLimits = true,
  onChange,
}: {
  field: ResourceField;
  value: number;
  min: number;
  max: number;
  allocated: number;
  showValueInput?: boolean;
  showLimits?: boolean;
  onChange: (value: number) => void;
}) {
  const [showTooltip, setShowTooltip] = React.useState(false);
  const safeMax = Math.max(min, max);
  const range = safeMax - min;
  const percent = range === 0 ? 0 : ((value - min) / range) * 100;
  const columns =
    showValueInput && showLimits
      ? "xl:grid-cols-[15rem_1fr_8rem_16rem]"
      : showValueInput
        ? "xl:grid-cols-[15rem_1fr_8rem]"
        : showLimits
          ? "xl:grid-cols-[15rem_1fr_16rem]"
          : "xl:grid-cols-[15rem_1fr]";

  return (
    <div
      className={`grid gap-4 rounded-lg border border-border px-4 py-4 xl:items-center ${columns}`}
    >
      <div className="flex items-center gap-3">
        <IconTile tone="neutral" className="h-11 w-11">
          {field.icon}
        </IconTile>
        <div>
          <div className="font-semibold text-text-primary">{field.label}</div>
          <div className="text-sm text-text-secondary">{field.description}</div>
        </div>
      </div>
      <div className="space-y-2">
        <div className="relative pt-8">
          <div
            className={`pointer-events-none absolute top-0 -translate-x-1/2 rounded-md bg-text-primary px-2 py-1 text-xs font-semibold text-surface shadow-sm transition-opacity ${
              showTooltip ? "opacity-100" : "opacity-0"
            }`}
            style={{
              left: `clamp(2rem, ${percent}%, calc(100% - 2rem))`,
            }}
          >
            {value} {field.unit}
          </div>
          <input
            type="range"
            min={min}
            max={safeMax}
            step={1}
            value={value}
            onPointerDown={() => setShowTooltip(true)}
            onPointerUp={() => setShowTooltip(false)}
            onPointerCancel={() => setShowTooltip(false)}
            onMouseEnter={() => setShowTooltip(true)}
            onMouseLeave={() => setShowTooltip(false)}
            onFocus={() => setShowTooltip(true)}
            onBlur={() => setShowTooltip(false)}
            onChange={(event) => onChange(Number(event.target.value))}
            className="h-2 w-full accent-primary"
            aria-label={field.label}
          />
        </div>
        <div className="flex justify-between text-xs font-medium text-text-secondary">
          <span>
            {min} {field.unit}
          </span>
          <span>
            {max} {field.unit}
          </span>
        </div>
      </div>
      {showValueInput ? (
        <label className="grid gap-1">
          <span className="sr-only">{field.label}</span>
          <span className="flex h-10 overflow-hidden rounded-md border border-border bg-surface">
            <input
              type="number"
              min={min}
              max={max}
              value={value}
              onChange={(event) => onChange(Number(event.target.value))}
              className="min-w-0 flex-1 border-0 bg-transparent px-3 text-sm font-medium text-text-primary focus:ring-0"
            />
            <span className="grid place-items-center border-l border-border px-3 text-sm text-text-secondary">
              {field.unit}
            </span>
          </span>
        </label>
      ) : null}
      {showLimits ? (
        <div className="grid gap-2 text-xs text-text-secondary">
          <ResourceLimit label="Total available" value={max} unit={field.unit} />
          <ResourceLimit
            label="Currently rented out"
            value={allocated}
            unit={field.unit}
          />
          <ResourceLimit
            label="Minimum configurable"
            value={min}
            unit={field.unit}
          />
        </div>
      ) : null}
    </div>
  );
}
