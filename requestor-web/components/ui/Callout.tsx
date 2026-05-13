"use client";

import React from "react";
import { RiInformationLine } from "@remixicon/react";
import { cn } from "./cn";

type CalloutTone = "info" | "warning" | "danger";

const TONE_CLASS: Record<CalloutTone, string> = {
  info: "bg-primary-soft text-text-secondary",
  warning: "border border-warning bg-warning-soft text-text-primary",
  danger: "border border-danger bg-danger-soft text-danger",
};

const ICON_CLASS: Record<CalloutTone, string> = {
  info: "text-primary",
  warning: "text-warning",
  danger: "text-danger",
};

export function Callout({
  tone = "info",
  className,
  children,
}: {
  tone?: CalloutTone;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div
      className={cn(
        "flex gap-3 rounded-md px-4 py-3 text-sm",
        TONE_CLASS[tone],
        className,
      )}
    >
      <RiInformationLine
        className={cn("mt-0.5 h-4 w-4 shrink-0", ICON_CLASS[tone])}
        aria-hidden
      />
      <span>{children}</span>
    </div>
  );
}
