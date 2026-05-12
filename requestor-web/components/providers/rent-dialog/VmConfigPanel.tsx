"use client";

import React from "react";
import { RiInformationLine } from "@remixicon/react";
import type { ProviderAd } from "../../../lib/api";
import type { RentSpec } from "./types";
import { ResourceStepper } from "./ResourceStepper";
import { SectionCard } from "./SectionCard";

export function VmConfigPanel({
  provider,
  spec,
  onSpecChange,
}: {
  provider: ProviderAd;
  spec: RentSpec;
  onSpecChange: (spec: RentSpec) => void;
}) {
  return (
    <SectionCard title="1. Configure VM">
      <div className="grid gap-3 sm:grid-cols-3">
        <ResourceStepper
          label="vCPU (Cores)"
          unit="cores"
          value={spec.cpu}
          max={provider.resources.cpu}
          onChange={(cpu) => onSpecChange({ ...spec, cpu })}
        />
        <ResourceStepper
          label="RAM (GB)"
          unit="GB"
          value={spec.memory}
          max={provider.resources.memory}
          onChange={(memory) => onSpecChange({ ...spec, memory })}
        />
        <ResourceStepper
          label="Storage (GB)"
          unit="GB"
          value={spec.storage}
          max={provider.resources.storage}
          onChange={(storage) => onSpecChange({ ...spec, storage })}
        />
      </div>
      <div className="mt-4 flex items-center gap-2 text-sm text-text-secondary">
        <span>
          Provider max: {provider.resources.cpu} vCPU, {provider.resources.memory} GB RAM,{" "}
          {provider.resources.storage} GB storage
        </span>
        <RiInformationLine className="h-4 w-4 shrink-0" aria-hidden />
      </div>
    </SectionCard>
  );
}
