"use client";

import React from "react";
import { RiCheckboxCircleLine } from "@remixicon/react";
import { cn } from "./cn";

export function StepProgress({
  steps,
  currentStep,
  label,
  onStepChange,
}: {
  steps: readonly string[];
  currentStep: number;
  label: string;
  onStepChange: (step: number) => void;
}) {
  return (
    <nav
      aria-label={label}
      className="overflow-x-auto border-b border-border px-5 py-4 md:border-b-0 md:border-r md:py-6"
    >
      <ol className="flex gap-4 md:block md:space-y-5">
        {steps.map((stepLabel, index) => {
          const complete = index < currentStep;
          const active = index === currentStep;
          return (
            <li key={stepLabel} className="flex items-center gap-3">
              <button
                type="button"
                className={cn(
                  "flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-xs font-medium transition",
                  active && "border-primary bg-primary text-white",
                  complete && "border-primary bg-primary-soft text-primary",
                  !active &&
                    !complete &&
                    "border-border-strong bg-surface text-text-secondary",
                )}
                onClick={() => {
                  if (index <= currentStep) onStepChange(index);
                }}
                disabled={index > currentStep}
                aria-current={active ? "step" : undefined}
              >
                {complete ? (
                  <RiCheckboxCircleLine className="h-4 w-4" aria-hidden />
                ) : (
                  index + 1
                )}
              </button>
              <span
                className={cn(
                  "whitespace-nowrap text-sm",
                  active || complete
                    ? "font-medium text-text-primary"
                    : "text-text-secondary",
                )}
              >
                {stepLabel}
              </span>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
