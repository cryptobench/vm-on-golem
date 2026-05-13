"use client";

import React from "react";
import { RiLockLine, RiShieldCheckLine } from "@remixicon/react";
import { Spinner } from "@golem/ui";

export function RentDialogFooter({
  disabled,
  creating,
  streamReady,
  disabledReason,
  onCancel,
  onCreate,
}: {
  disabled: boolean;
  creating: boolean;
  streamReady: boolean;
  disabledReason: string;
  onCancel: () => void;
  onCreate: () => void;
}) {
  return (
    <div className="border-t border-border px-6 py-4">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex items-center gap-4">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md border border-border bg-surface-muted text-text-secondary">
            <RiShieldCheckLine className="h-5 w-5" aria-hidden />
          </div>
          <div>
            <div className="text-sm font-semibold text-text-primary">Secure and decentralized</div>
            <div className="text-sm text-text-secondary">Payments are handled by StreamPayment smart contracts.</div>
          </div>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <button className="btn btn-secondary min-w-32" type="button" onClick={onCancel} disabled={creating}>
            Cancel
          </button>
          <button
            className="btn btn-primary min-w-64 disabled:cursor-not-allowed disabled:opacity-60"
            type="button"
            onClick={onCreate}
            disabled={disabled || creating}
          >
            {creating ? (
              <span className="inline-flex items-center gap-2">
                <Spinner className="h-4 w-4 text-white" />
                Creating...
              </span>
            ) : (
              <span className="inline-flex items-center gap-2">
                <RiLockLine className="h-4 w-4" aria-hidden />
                {streamReady ? "Create VM" : "Review & Create VM"}
              </span>
            )}
          </button>
        </div>
      </div>
      {disabled && !creating ? (
        <div className="mt-3 text-right text-sm text-text-secondary">{disabledReason}</div>
      ) : null}
    </div>
  );
}
