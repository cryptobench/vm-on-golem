"use client";

import React from "react";
import {
  RiCloseLine,
  RiCpuLine,
  RiDatabase2Line,
  RiInformationLine,
  RiRam2Line,
} from "@remixicon/react";
import { Button } from "../../ui/Button";
import { Modal } from "../../ui/Modal";
import { NumberStepper } from "./VmDetailPrimitives";

type ResizeResources = {
  cpu: number;
  memory: number;
  storage: number;
};

export function VmResizeModal({
  open,
  current,
  next,
  transitioning,
  busy,
  limits,
  phase,
  onClose,
  onCpuChange,
  onMemoryChange,
  onStorageChange,
  onResize,
}: {
  open: boolean;
  current: ResizeResources;
  next: ResizeResources;
  transitioning?: boolean;
  busy?: boolean;
  limits: ResizeResources;
  phase?: string | null;
  onClose: () => void;
  onCpuChange: (value: number) => void;
  onMemoryChange: (value: number) => void;
  onStorageChange: (value: number) => void;
  onResize: () => void;
}) {
  const blocked = !!transitioning;
  const unchanged =
    current.cpu === next.cpu &&
    current.memory === next.memory &&
    current.storage === next.storage;
  const disabled = blocked || unchanged || !!busy;
  const disabledReason = unchanged
    ? "Change at least one resource to resize."
    : blocked
      ? "Wait for the current VM transition to finish."
      : undefined;

  return (
    <Modal open={open} onClose={busy ? () => undefined : onClose} size="xl">
      <div className="p-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-text-primary">
              Resize VM
            </h2>
            <p className="mt-3 text-sm leading-5 text-text-secondary">
              Resize will stop this VM, apply the new resources, then restart it
              if it was running.
            </p>
          </div>
          <button
            type="button"
            className="inline-flex h-8 w-8 items-center justify-center rounded-md text-text-muted transition hover:bg-surface-muted hover:text-text-primary"
            onClick={onClose}
            disabled={busy}
            aria-label="Close resize dialog"
          >
            <RiCloseLine className="h-5 w-5" aria-hidden />
          </button>
        </div>

        <div className="mt-6 grid grid-cols-[minmax(0,1fr)_7rem_minmax(9rem,12rem)] border-b border-border pb-3 text-xs font-medium text-text-muted">
          <div>Resource</div>
          <div>Current</div>
          <div>New</div>
        </div>

        <div className="divide-y divide-border">
          <ResourceRow
            icon={<RiCpuLine className="h-5 w-5" aria-hidden />}
            label="vCPU"
            current={`${current.cpu} vCPU`}
            control={
              <NumberStepper
                label="vCPU"
                value={next.cpu}
                min={1}
                max={limits.cpu}
                disabled={busy}
                onChange={onCpuChange}
                hideLabel
              />
            }
            helper={`Min 1 · Max ${limits.cpu}`}
          />
          <ResourceRow
            icon={<RiRam2Line className="h-5 w-5" aria-hidden />}
            label="RAM (GB)"
            current={`${current.memory} GB`}
            control={
              <NumberStepper
                label="RAM"
                value={next.memory}
                min={1}
                max={limits.memory}
                disabled={busy}
                onChange={onMemoryChange}
                hideLabel
              />
            }
            helper={`Min 1 GB · Max ${limits.memory} GB`}
          />
          <ResourceRow
            icon={<RiDatabase2Line className="h-5 w-5" aria-hidden />}
            label="Storage (GB)"
            current={`${current.storage} GB`}
            control={
              <NumberStepper
                label="Storage"
                value={next.storage}
                min={current.storage}
                max={limits.storage}
                disabled={busy}
                onChange={onStorageChange}
                hideLabel
              />
            }
            helper={`Min ${current.storage} GB · Max ${limits.storage} GB`}
          />
        </div>

        <div className="mt-5 flex items-center gap-2 rounded-md bg-surface-muted px-3 py-2 text-sm text-text-secondary">
          <RiInformationLine
            className="h-4 w-4 shrink-0 text-primary"
            aria-hidden
          />
          <span>
            {busy && phase
              ? phase
              : blocked
                ? "Wait for the current VM transition to finish before resizing."
                : "Storage can only be increased."}
          </span>
        </div>

        <div className="mt-5 flex justify-end gap-3">
          <Button
            variant="secondary"
            className="px-6"
            onClick={onClose}
            disabled={busy}
          >
            Cancel
          </Button>
          <Button
            variant="primary"
            className="min-w-56 px-6"
            onClick={onResize}
            disabled={disabled}
            busy={!!busy}
            title={disabledReason}
            aria-disabled={disabled}
          >
            {busy ? "Resizing" : "Resize VM"}
          </Button>
        </div>
      </div>
    </Modal>
  );
}

function ResourceRow({
  icon,
  label,
  current,
  control,
  helper,
}: {
  icon: React.ReactNode;
  label: string;
  current: string;
  control: React.ReactNode;
  helper: string;
}) {
  return (
    <div className="grid grid-cols-[minmax(0,1fr)_7rem_minmax(9rem,12rem)] items-center gap-4 py-4">
      <div className="flex min-w-0 items-center gap-3 text-sm font-medium text-text-primary">
        <span className="text-text-muted">{icon}</span>
        <span className="truncate">{label}</span>
      </div>
      <div className="text-sm font-medium text-text-primary">{current}</div>
      <div className="min-w-0">
        {control}
        <div className="mt-2 text-xs text-text-muted">{helper}</div>
      </div>
    </div>
  );
}
