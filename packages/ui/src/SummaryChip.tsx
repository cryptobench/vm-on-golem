"use client";

import React from "react";
import type { RemixiconComponentType } from "@remixicon/react";

export function SummaryChip({
  icon: Icon,
  label,
}: {
  icon: RemixiconComponentType;
  label: string;
}) {
  return (
    <span className="flex min-w-0 items-center gap-2">
      <Icon className="h-4 w-4 shrink-0 text-text-secondary" aria-hidden />
      <span className="truncate">{label}</span>
    </span>
  );
}
