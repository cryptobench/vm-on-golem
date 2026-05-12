"use client";

import React from "react";
import { RiComputerLine, RiUbuntuLine, RiWindowsLine } from "@remixicon/react";

export function VmPlatform({ platform }: { platform?: string | null }) {
  const normalized = String(platform || "").toLowerCase();
  const Icon = normalized.includes("win")
    ? RiWindowsLine
    : normalized.includes("linux") || normalized.includes("ubuntu")
      ? RiUbuntuLine
      : RiComputerLine;
  const label = platform || "Unknown";

  return (
    <span className="inline-flex items-center gap-2 text-sm text-text-primary">
      <Icon className="h-4 w-4 shrink-0 text-primary" aria-hidden />
      <span className="truncate">{label}</span>
    </span>
  );
}
