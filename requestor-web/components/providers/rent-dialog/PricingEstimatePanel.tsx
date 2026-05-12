"use client";

import React from "react";
import { RiInformationLine } from "@remixicon/react";
import { humanDuration } from "../../../lib/streams";
import type { PriceLine } from "./types";

function AmountBlock({ label, line }: { label: string; line: PriceLine }) {
  return (
    <div>
      <div className="text-sm text-text-secondary">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-text-primary">{line.primary}</div>
      {line.secondary ? <div className="mt-1 text-sm text-text-secondary">approx. {line.secondary}</div> : null}
    </div>
  );
}

export function PricingEstimatePanel({
  hourly,
  monthly,
  deposit,
  durationSeconds,
}: {
  hourly: PriceLine;
  monthly: PriceLine;
  deposit: PriceLine;
  durationSeconds: number;
}) {
  return (
    <aside className="rounded-lg border border-border bg-surface p-5">
      <div className="flex items-center gap-2">
        <h3 className="text-base font-semibold text-text-primary">Pricing estimate</h3>
        <RiInformationLine className="h-4 w-4 text-text-secondary" aria-hidden />
      </div>
      <div className="mt-7 space-y-7">
        <AmountBlock label="Estimated hourly price" line={hourly} />
        <AmountBlock label="Estimated monthly price" line={monthly} />
        <div className="border-t border-border pt-7">
          <AmountBlock
            label={`Initial deposit (${durationSeconds > 0 ? humanDuration(durationSeconds) : "duration required"})`}
            line={deposit}
          />
          <p className="mt-3 text-sm text-text-secondary">
            Deposit covers compute usage for the selected duration.
          </p>
        </div>
      </div>
      <div className="mt-8 rounded-md bg-primary-soft px-4 py-3 text-sm text-text-secondary">
        Unused balance remains in the stream and can be used to extend it.
      </div>
      <div className="mt-8">
        <div className="text-sm font-semibold text-text-primary">What happens next?</div>
        <ol className="mt-4 space-y-4 text-sm text-text-secondary">
          {[
            "A StreamPayment stream is opened on your behalf.",
            "The stream is funded for the selected duration.",
            "Your VM is created and becomes available from My VMs.",
          ].map((item, index) => (
            <li key={item} className="flex gap-3">
              <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-border text-xs">
                {index + 1}
              </span>
              <span>{item}</span>
            </li>
          ))}
        </ol>
      </div>
    </aside>
  );
}
