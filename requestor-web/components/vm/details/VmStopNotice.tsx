"use client";

import React from "react";
import { RiErrorWarningLine } from "@remixicon/react";
import { Spinner } from "../../ui/Spinner";

export function VmStopNotice({
  running,
  busy,
  onStop,
}: {
  running: boolean;
  busy?: boolean;
  onStop: () => void;
}) {
  if (!running) return null;

  return (
    <div className="vm-page-enter flex flex-col gap-3 rounded-lg border border-warning-soft bg-warning-soft p-4 text-sm text-text-primary sm:flex-row sm:items-center sm:justify-between">
      <div className="flex gap-3">
        <RiErrorWarningLine className="mt-0.5 h-5 w-5 shrink-0 text-warning" aria-hidden />
        <div>
          <div className="font-semibold">Some features are unavailable while the VM is running.</div>
          <div className="mt-1 text-text-secondary">
            To create/restore snapshots or resize the VM, please stop it first.
          </div>
        </div>
      </div>
      <button
        type="button"
        className="btn border-warning bg-surface px-8 text-warning ring-warning hover:bg-warning-soft"
        onClick={onStop}
        disabled={busy}
      >
        {busy ? <Spinner className="h-4 w-4" /> : "Stop VM"}
      </button>
    </div>
  );
}
