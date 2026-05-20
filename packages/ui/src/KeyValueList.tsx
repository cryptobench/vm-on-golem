"use client";

import React from "react";
import { cn } from "./cn";

export type KeyValueItem = {
  key: string;
  label: React.ReactNode;
  value: React.ReactNode;
  icon?: React.ReactNode;
};

export function KeyValueList({
  items,
  className,
}: {
  items: KeyValueItem[];
  className?: string;
}) {
  return (
    <div className={cn("divide-y divide-border", className)}>
      {items.map((item) => (
        <div
          key={item.key}
          className="grid min-h-10 grid-cols-[minmax(0,1fr)_minmax(0,1fr)] items-center gap-4 py-2 text-sm"
        >
          <div className="flex min-w-0 items-center gap-3 text-text-secondary">
            {item.icon ? <span className="shrink-0 text-text-muted">{item.icon}</span> : null}
            <span className="truncate">{item.label}</span>
          </div>
          <div className="min-w-0 overflow-hidden text-right font-medium text-text-primary">
            {item.value}
          </div>
        </div>
      ))}
    </div>
  );
}
