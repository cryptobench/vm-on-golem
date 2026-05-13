"use client";

import React from "react";
import { RiMoreLine } from "@remixicon/react";
import { cn } from "./cn";

export type ActionMenuItem = {
  label: string;
  onSelect: () => void;
  disabled?: boolean;
  tone?: "neutral" | "danger";
};

export function ActionMenu({
  items,
  label = "Actions",
  className,
}: {
  items: ActionMenuItem[];
  label?: string;
  className?: string;
}) {
  const [open, setOpen] = React.useState(false);
  const rootRef = React.useRef<HTMLDivElement | null>(null);

  React.useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    window.addEventListener("pointerdown", onPointerDown);
    return () => window.removeEventListener("pointerdown", onPointerDown);
  }, [open]);

  return (
    <div ref={rootRef} className={cn("relative inline-flex", className)}>
      <button
        type="button"
        aria-label={label}
        title={label}
        className="grid h-8 w-8 place-items-center rounded-md text-text-secondary transition hover:bg-surface-muted hover:text-text-primary focus:outline-none focus:ring-2 focus:ring-primary"
        onClick={(event) => {
          event.stopPropagation();
          setOpen((value) => !value);
        }}
      >
        <RiMoreLine className="h-4 w-4" aria-hidden />
      </button>
      {open ? (
        <div className="absolute right-0 top-9 z-20 min-w-40 rounded-lg bg-surface p-1 shadow-popover ring-1 ring-border">
          {items.map((item) => (
            <button
              key={item.label}
              type="button"
              className={cn(
                "block h-9 w-full rounded-md px-3 text-left text-sm transition hover:bg-surface-muted disabled:cursor-not-allowed disabled:opacity-50",
                item.tone === "danger" ? "text-danger" : "text-text-primary",
              )}
              disabled={item.disabled}
              onClick={(event) => {
                event.stopPropagation();
                setOpen(false);
                item.onSelect();
              }}
            >
              {item.label}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
