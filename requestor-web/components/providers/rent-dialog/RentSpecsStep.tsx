"use client";

import React from "react";
import {
  RiCpuLine,
  RiDatabase2Line,
  RiInformationLine,
  RiRamLine,
} from "@remixicon/react";
import type { RemixiconComponentType } from "@remixicon/react";
import type { ProviderAd } from "../../../lib/api";
import { NumberStepper } from "../../ui/NumberStepper";
import type { RentSpec } from "./types";
import { RentStepSection } from "./RentStepSection";

export function RentSpecsStep({
  provider,
  spec,
  onSpecChange,
}: {
  provider: ProviderAd;
  spec: RentSpec;
  onSpecChange: (spec: RentSpec) => void;
}) {
  return (
    <RentStepSection
      title="Choose your specs"
      description="Select the resources your VM will have."
    >
      <div className="mt-8 space-y-8">
        <SpecRow
          icon={RiCpuLine}
          label="vCPU (Cores)"
          value={spec.cpu}
          unit="vCPU"
          min={1}
          max={provider.resources.cpu}
          onChange={(cpu) => onSpecChange({ ...spec, cpu })}
        />
        <SpecRow
          icon={RiRamLine}
          label="RAM (GB)"
          value={spec.memory}
          unit="GB"
          min={1}
          max={provider.resources.memory}
          onChange={(memory) => onSpecChange({ ...spec, memory })}
        />
        <SpecRow
          icon={RiDatabase2Line}
          label="Storage (GB)"
          value={spec.storage}
          unit="GB"
          min={1}
          max={provider.resources.storage}
          onChange={(storage) => onSpecChange({ ...spec, storage })}
        />
      </div>
    </RentStepSection>
  );
}

function SpecRow({
  icon: Icon,
  label,
  value,
  unit,
  min,
  max,
  onChange,
}: {
  icon: RemixiconComponentType;
  label: string;
  value: number;
  unit: string;
  min: number;
  max: number;
  onChange: (value: number) => void;
}) {
  const safeMax = Math.max(min, Math.floor(max || min));
  return (
    <div className="grid gap-4 sm:grid-cols-[11rem_10rem_minmax(12rem,1fr)] sm:items-center">
      <div className="flex min-w-0 items-center gap-4">
        <Icon className="h-5 w-5 shrink-0 text-text-secondary" aria-hidden />
        <div className="min-w-0 text-sm font-semibold text-text-primary">
          {label}
        </div>
      </div>
      <div className="w-40">
        <NumberStepper
          label={label}
          value={value}
          min={min}
          max={safeMax}
          onChange={onChange}
          hideLabel
        />
      </div>
      <div className="flex flex-wrap items-center gap-x-1 gap-y-1 text-xs text-text-secondary">
        <span>
          Min {min} {unit} - Max {safeMax} {unit}
        </span>
        {label.startsWith("Storage") ? (
          <span className="inline-flex items-center gap-1">
            Storage can only be increased later
            <RiInformationLine className="h-3.5 w-3.5" aria-hidden />
          </span>
        ) : null}
      </div>
    </div>
  );
}
