"use client";

import React from "react";
import { humanDuration } from "../../lib/streams";
import { cn } from "@golem/ui";
import { remainingSeconds, streamRunwayPercent, type StreamRow } from "./streamModel";

export function StreamRunway({
  row,
  nowSec,
  className,
}: {
  row: StreamRow;
  nowSec: number;
  className?: string;
}) {
  const percent = streamRunwayPercent(row, nowSec);
  const urgent = percent < 18;
  const remaining = humanDuration(remainingSeconds(row, nowSec));

  return (
    <div className={cn("min-w-36", className)}>
      <div className="font-medium text-text-primary">{remaining}</div>
      <div className="mt-2 flex items-center gap-3">
        <div className="h-1.5 w-20 overflow-hidden rounded-md bg-surface-muted">
          <div
            className={cn(
              "streams-runway-bar h-full rounded-md",
              urgent ? "bg-danger" : "bg-success",
            )}
            style={{ width: `${percent}%` }}
          />
        </div>
        <span className="text-xs text-text-secondary">{Math.round(percent)}%</span>
      </div>
    </div>
  );
}
