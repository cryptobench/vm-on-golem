"use client";

import React from "react";
import { cn } from "./cn";

export function FormField({
  label,
  children,
  hint,
  className,
}: {
  label: string;
  children: React.ReactNode;
  hint?: React.ReactNode;
  className?: string;
}) {
  return (
    <label className={cn("block", className)}>
      <span className="label">{label}</span>
      <span className="mt-2 block">{children}</span>
      {hint ? <span className="mt-2 block text-sm text-text-secondary">{hint}</span> : null}
    </label>
  );
}
