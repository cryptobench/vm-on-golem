"use client";

import React from "react";
import { createPortal } from "react-dom";
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
  const [menuPosition, setMenuPosition] = React.useState<{
    left: number;
    top: number;
  } | null>(null);
  const rootRef = React.useRef<HTMLDivElement | null>(null);
  const buttonRef = React.useRef<HTMLButtonElement | null>(null);
  const menuRef = React.useRef<HTMLDivElement | null>(null);

  const updateMenuPosition = React.useCallback(() => {
    const trigger = buttonRef.current;
    if (!trigger || typeof window === "undefined") return;

    const rect = trigger.getBoundingClientRect();
    const menuWidth = menuRef.current?.offsetWidth ?? 160;
    const menuHeight = menuRef.current?.offsetHeight ?? 0;
    const viewportGap = 8;
    const triggerGap = 6;

    const maxLeft = Math.max(
      viewportGap,
      window.innerWidth - menuWidth - viewportGap,
    );
    const left = Math.min(
      Math.max(viewportGap, rect.right - menuWidth),
      maxLeft,
    );
    let top = rect.bottom + triggerGap;

    if (menuHeight > 0 && top + menuHeight > window.innerHeight - viewportGap) {
      top = Math.max(viewportGap, rect.top - menuHeight - triggerGap);
    }

    setMenuPosition({ left, top });
  }, []);

  React.useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      const target = event.target as Node;
      if (
        !rootRef.current?.contains(target) &&
        !menuRef.current?.contains(target)
      ) {
        setOpen(false);
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };

    window.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("resize", updateMenuPosition);
    window.addEventListener("scroll", updateMenuPosition, true);

    return () => {
      window.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("resize", updateMenuPosition);
      window.removeEventListener("scroll", updateMenuPosition, true);
    };
  }, [open, updateMenuPosition]);

  React.useLayoutEffect(() => {
    if (open) updateMenuPosition();
  }, [open, updateMenuPosition]);

  return (
    <div ref={rootRef} className={cn("relative inline-flex", className)}>
      <button
        ref={buttonRef}
        type="button"
        aria-label={label}
        aria-expanded={open}
        aria-haspopup="menu"
        title={label}
        className="grid h-8 w-8 place-items-center rounded-md text-text-secondary transition hover:bg-surface-muted hover:text-text-primary focus:outline-none focus:ring-2 focus:ring-primary"
        onClick={(event) => {
          event.stopPropagation();
          if (!open) updateMenuPosition();
          setOpen((value) => !value);
        }}
      >
        <RiMoreLine className="h-4 w-4" aria-hidden />
      </button>
      {open && menuPosition && typeof document !== "undefined"
        ? createPortal(
            <div
              ref={menuRef}
              role="menu"
              className="fixed z-[120] min-w-40 rounded-lg bg-surface p-1 shadow-popover ring-1 ring-border"
              style={{
                left: menuPosition.left,
                top: menuPosition.top,
              }}
            >
              {items.map((item) => (
                <button
                  key={item.label}
                  type="button"
                  role="menuitem"
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
            </div>,
            document.body,
          )
        : null}
    </div>
  );
}
