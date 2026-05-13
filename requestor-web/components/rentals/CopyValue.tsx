"use client";

import React from "react";
import { RiFileCopyLine } from "@remixicon/react";
import { useToast } from "@golem/ui";
import { cn } from "@golem/ui";

function compactValue(value: string) {
  if (value.length <= 12) return value;
  return `${value.slice(0, 5)}...${value.slice(-4)}`;
}

export function CopyValue({
  value,
  empty = "-",
  className,
}: {
  value?: string | number | null;
  empty?: string;
  className?: string;
}) {
  const { show } = useToast();
  const text = value == null || value === "" ? "" : String(value);

  const copy = async (event: React.MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      show("Copied to clipboard");
    } catch (error) {
      show(error instanceof Error ? error.message : String(error));
    }
  };

  if (!text)
    return <span className={cn("text-text-muted", className)}>{empty}</span>;

  return (
    <span
      className={cn("inline-flex min-w-0 items-center gap-2", className)}
      title={text}
    >
      <span className="truncate font-mono text-xs">{compactValue(text)}</span>
      <button
        className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-text-muted transition hover:bg-surface-muted hover:text-primary focus:outline-none focus:ring-2 focus:ring-primary"
        onClick={copy}
        type="button"
        aria-label="Copy value"
      >
        <RiFileCopyLine className="h-4 w-4" aria-hidden />
      </button>
    </span>
  );
}
