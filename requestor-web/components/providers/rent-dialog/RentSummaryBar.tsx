"use client";

import React from "react";
import {
  RiCalendarLine,
  RiCpuLine,
  RiDatabase2Line,
  RiRamLine,
} from "@remixicon/react";
import { Button } from "../../ui/Button";
import { Spinner } from "../../ui/Spinner";
import { SummaryChip } from "../../ui/SummaryChip";
import { RENT_STEPS } from "./constants";
import type { RentSpec } from "./types";

export function RentSummaryBar({
  step,
  spec,
  durationLabel,
  estimateLabel,
  estimatePrimary,
  estimateSecondary,
  creating,
  phase,
  disabledReason,
  onCancel,
  onBack,
  onContinue,
  actionDisabled,
}: {
  step: number;
  spec: RentSpec;
  durationLabel: string;
  estimateLabel: string;
  estimatePrimary: string;
  estimateSecondary: string;
  creating: boolean;
  phase: string;
  disabledReason: string;
  onCancel: () => void;
  onBack: () => void;
  onContinue: () => void;
  actionDisabled: boolean;
}) {
  return (
    <div className="shrink-0 border-t border-border px-6 py-4 sm:px-8">
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_10rem_auto] lg:items-center">
        <div className="min-w-0">
          <div className="text-xs font-semibold text-text-primary">Summary</div>
          <div className="mt-2 grid gap-3 text-xs text-text-primary sm:grid-cols-4">
            <SummaryChip icon={RiCpuLine} label={`${spec.cpu} vCPU`} />
            <SummaryChip icon={RiRamLine} label={`${spec.memory} GB RAM`} />
            <SummaryChip
              icon={RiDatabase2Line}
              label={`${spec.storage} GB Storage`}
            />
            <SummaryChip
              icon={RiCalendarLine}
              label={step === 0 ? "-" : durationLabel}
            />
          </div>
          {creating && phase ? (
            <div className="mt-2 inline-flex items-center gap-2 text-sm text-text-secondary">
              <Spinner className="h-4 w-4 text-primary" />
              {phase}
            </div>
          ) : disabledReason ? (
            <div className="mt-2 text-sm text-text-secondary">
              {disabledReason}
            </div>
          ) : null}
        </div>
        <div className="border-border lg:border-l lg:pl-6">
          <div className="text-xs font-semibold text-text-secondary">
            {estimateLabel}
          </div>
          <div className="mt-1 text-xl font-semibold text-text-primary">
            {estimatePrimary}
          </div>
          <div className="text-xs text-text-secondary">
            approx. {estimateSecondary}
          </div>
        </div>
        <div className="flex gap-3 lg:justify-end">
          <Button
            variant="secondary"
            className="min-w-28"
            onClick={step === 0 ? onCancel : onBack}
            disabled={creating}
          >
            Back
          </Button>
          <Button
            className="min-w-36"
            onClick={onContinue}
            disabled={actionDisabled}
            busy={creating}
          >
            {step === RENT_STEPS.length - 1 ? "Create VM" : "Continue"}
          </Button>
        </div>
      </div>
    </div>
  );
}
