"use client";

import React from "react";
import { RiErrorWarningLine } from "@remixicon/react";
import { Spinner } from "../../ui/Spinner";
import {
  DetailPanel,
  NumberStepper,
  PanelTitle,
} from "./VmDetailPrimitives";

export function VmResizePanel({
  cpu,
  memory,
  storage,
  minStorage,
  stopped,
  busy,
  onCpuChange,
  onMemoryChange,
  onStorageChange,
  onResize,
}: {
  cpu: number;
  memory: number;
  storage: number;
  minStorage: number;
  stopped: boolean;
  busy?: boolean;
  onCpuChange: (value: number) => void;
  onMemoryChange: (value: number) => void;
  onStorageChange: (value: number) => void;
  onResize: () => void;
}) {
  const disabled = !stopped || busy;

  return (
    <DetailPanel className="vm-page-enter">
      <PanelTitle
        title="Resize"
        hint="VM must be stopped. Storage can only be increased."
      />
      <div className="mt-5 grid gap-4">
        <NumberStepper
          label="vCPU"
          value={cpu}
          min={1}
          disabled={disabled}
          onChange={onCpuChange}
        />
        <NumberStepper
          label="RAM (GB)"
          value={memory}
          min={1}
          disabled={disabled}
          onChange={onMemoryChange}
        />
        <NumberStepper
          label="Storage (GB)"
          value={storage}
          min={minStorage}
          disabled={disabled}
          onChange={onStorageChange}
        />
        <button
          type="button"
          className="btn btn-primary w-full gap-2"
          onClick={onResize}
          disabled={disabled}
        >
          {busy && <Spinner className="h-4 w-4 text-white" />}
          Resize VM
        </button>
      </div>
      {!stopped && (
        <div className="mt-4 flex gap-2 rounded-md border border-danger-soft bg-danger-soft p-3 text-sm text-danger">
          <RiErrorWarningLine className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          <span>Resize can only be performed when the VM is stopped.</span>
        </div>
      )}
    </DetailPanel>
  );
}
