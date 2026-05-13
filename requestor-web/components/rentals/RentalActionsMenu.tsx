"use client";

import React from "react";
import {
  RiArrowDownSLine,
  RiDeleteBinLine,
  RiEyeLine,
  RiFileCopyLine,
  RiPauseLine,
  RiPlayLine,
} from "@remixicon/react";
import type { Rental } from "../../lib/api";
import { ConfirmDialog } from "../ui/ConfirmDialog";
import { Spinner } from "../ui/Spinner";
import { cn } from "../ui/cn";

type RentalActionsMenuProps = {
  rental: Rental;
  status: string;
  busy?: boolean;
  onView: () => void;
  onCopySSH?: (rental: Rental) => void;
  onStart?: (rental: Rental) => void;
  onStop?: (rental: Rental) => void;
  onDestroy?: (rental: Rental) => void;
};

function isTerminated(status: string) {
  return status === "terminated" || status === "deleted";
}

function isProviderOffline(status: string) {
  return status === "offline";
}

export function RentalActionsMenu({
  rental,
  status,
  busy,
  onView,
  onCopySSH,
  onStart,
  onStop,
  onDestroy,
}: RentalActionsMenuProps) {
  const [open, setOpen] = React.useState(false);
  const [confirmOpen, setConfirmOpen] = React.useState(false);
  const ref = React.useRef<HTMLDivElement | null>(null);
  const terminal = isTerminated(status);
  const providerOffline = isProviderOffline(status);
  const canStart =
    !terminal &&
    !providerOffline &&
    (status === "stopped" || status === "suspended");
  const canStop = !terminal && !providerOffline && status === "running";
  const startLabel = status === "suspended" ? "Resume" : "Start";

  React.useEffect(() => {
    const close = (event: MouseEvent) => {
      if (!ref.current?.contains(event.target as Node)) setOpen(false);
    };
    if (open) document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  const choose = (action: () => void) => (event: React.MouseEvent) => {
    event.stopPropagation();
    setOpen(false);
    action();
  };

  return (
    <>
      <div className="relative z-40 flex justify-end" ref={ref}>
        {canStart ? (
          <div className="inline-flex h-10 rounded-md shadow-soft">
            <button
              className="btn btn-primary rounded-r-none px-4"
              onClick={choose(() => onStart?.(rental))}
              disabled={busy}
              type="button"
            >
              {busy ? (
                <Spinner className="h-4 w-4 text-white" />
              ) : (
                <RiPlayLine className="h-4 w-4" aria-hidden />
              )}
              <span className="ml-2">{startLabel}</span>
            </button>
            <button
              className="btn btn-primary rounded-l-none border-l border-primary-hover px-2"
              onClick={(event) => {
                event.stopPropagation();
                setOpen((current) => !current);
              }}
              disabled={busy}
              type="button"
              aria-label="Open VM actions"
              aria-expanded={open}
            >
              <RiArrowDownSLine className="h-5 w-5" aria-hidden />
            </button>
          </div>
        ) : (
          <button
            className="btn btn-secondary gap-2 px-3"
            onClick={(event) => {
              event.stopPropagation();
              setOpen((current) => !current);
            }}
            disabled={busy}
            type="button"
            aria-label="Open VM actions"
            aria-expanded={open}
          >
            {busy ? (
              <Spinner className="h-4 w-4 text-primary" />
            ) : (
              <>
                Actions
                <RiArrowDownSLine className="h-4 w-4" aria-hidden />
              </>
            )}
          </button>
        )}

        {open && (
          <div
            className="vm-action-menu absolute right-0 top-12 z-50 w-56 rounded-lg border border-border bg-surface py-1 shadow-popover"
            onClick={(event) => event.stopPropagation()}
          >
            <button
              className="vm-action-menu__item"
              onClick={choose(onView)}
              type="button"
            >
              <RiEyeLine className="h-4 w-4" aria-hidden />
              View details
            </button>
            {!terminal && !providerOffline && onCopySSH && (
              <button
                className="vm-action-menu__item"
                onClick={choose(() => onCopySSH(rental))}
                type="button"
              >
                <RiFileCopyLine className="h-4 w-4" aria-hidden />
                Copy SSH command
              </button>
            )}
            {canStop && onStop && (
              <button
                className="vm-action-menu__item"
                onClick={choose(() => onStop(rental))}
                type="button"
              >
                <RiPauseLine className="h-4 w-4" aria-hidden />
                Stop
              </button>
            )}
            {!terminal && onDestroy && (
              <button
                className={cn(
                  "vm-action-menu__item text-danger hover:bg-danger-soft",
                )}
                onClick={choose(() => setConfirmOpen(true))}
                type="button"
              >
                <RiDeleteBinLine className="h-4 w-4" aria-hidden />
                Terminate
              </button>
            )}
          </div>
        )}
      </div>

      <ConfirmDialog
        open={confirmOpen}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={() => {
          setConfirmOpen(false);
          onDestroy?.(rental);
        }}
        title="Terminate VM"
        description="Are you sure you want to permanently terminate this VM? This action cannot be undone."
        confirmLabel="Terminate"
        danger
        busy={!!busy}
      />
    </>
  );
}
