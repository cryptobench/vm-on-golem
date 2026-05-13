"use client";

import React from "react";
import { RiCheckboxCircleLine } from "@remixicon/react";
import { cn } from "./cn";

export function SelectableCard({
  selected,
  children,
  className,
  onClick,
}: {
  selected: boolean;
  children: React.ReactNode;
  className?: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className={cn(
        "relative flex min-h-28 flex-col items-center justify-center rounded-md border border-border bg-surface px-4 py-4 text-center transition hover:border-border-strong hover:bg-surface-muted",
        selected && "border-primary ring-1 ring-primary",
        className,
      )}
      onClick={onClick}
    >
      {selected ? (
        <RiCheckboxCircleLine
          className="absolute right-3 top-3 h-5 w-5 text-primary"
          aria-hidden
        />
      ) : null}
      {children}
    </button>
  );
}
