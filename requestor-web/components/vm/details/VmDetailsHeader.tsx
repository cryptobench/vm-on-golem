"use client";

import React from "react";
import { Menu, Transition } from "@headlessui/react";
import {
  RiArrowDownSLine,
  RiArrowRightSLine,
  RiComputerLine,
  RiRefreshLine,
  RiTerminalLine,
} from "@remixicon/react";
import { StatusBadge } from "../../ui/StatusBadge";
import { Spinner } from "../../ui/Spinner";
import { cn } from "../../ui/cn";

export type VmAction = {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  danger?: boolean;
};

export function VmDetailsHeader({
  name,
  status,
  statusMessage,
  lifecycleStage,
  progress,
  transitioning,
  lastUpdated,
  copySshDisabled,
  busy,
  actions,
  onCopySsh,
}: {
  name: string;
  status: string;
  statusMessage?: string | null;
  lifecycleStage?: string | null;
  progress?: number | null;
  transitioning?: boolean;
  lastUpdated?: string | null;
  copySshDisabled?: boolean;
  busy?: boolean;
  actions: VmAction[];
  onCopySsh: () => void;
}) {
  const showProgress = Boolean(transitioning && progress != null);
  const progressValue = Math.max(0, Math.min(100, Math.round(progress || 0)));

  return (
    <header className="vm-page-enter relative z-40 flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
      <div className="min-w-0">
        <div className="flex items-center gap-2 text-xs font-medium text-text-muted">
          <span>My VMs</span>
          <RiArrowRightSLine className="h-4 w-4" aria-hidden />
          <span className="truncate text-text-primary">{name}</span>
        </div>
        <div className="mt-3 flex min-w-0 flex-wrap items-center gap-3">
          <h1 className="truncate text-2xl font-semibold text-text-primary">
            {name}
          </h1>
          <StatusBadge status={status} />
        </div>
        <div className="mt-2 flex items-center gap-2 text-sm text-text-secondary">
          <span>{statusMessage || "Checking provider status"}</span>
          {lifecycleStage && lifecycleStage !== status ? (
            <>
              <span aria-hidden>&middot;</span>
              <span>{formatStage(lifecycleStage)}</span>
            </>
          ) : null}
          {showProgress ? (
            <>
              <span aria-hidden>&middot;</span>
              <span>{progressValue}%</span>
            </>
          ) : null}
          <span aria-hidden>&middot;</span>
          <span>Updated {lastUpdated || "just now"}</span>
          <RiRefreshLine className="h-4 w-4 text-text-muted" aria-hidden />
        </div>
        {showProgress ? (
          <div className="mt-3 h-1.5 w-full max-w-xl overflow-hidden rounded-full bg-surface-muted">
            <div
              className="h-full rounded-full bg-warning transition-all duration-500"
              style={{ width: `${progressValue}%` }}
            />
          </div>
        ) : null}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          className="btn btn-secondary gap-2"
          onClick={onCopySsh}
          disabled={copySshDisabled}
        >
          <RiTerminalLine className="h-5 w-5" aria-hidden />
          Copy SSH command
        </button>
        <Menu as="div" className="relative z-50">
          <Menu.Button className="btn btn-primary gap-2 px-5" disabled={busy}>
            {busy && <Spinner className="h-4 w-4 text-white" />}
            Actions
            <RiArrowDownSLine className="h-5 w-5" aria-hidden />
          </Menu.Button>
          <Transition
            as={React.Fragment}
            enter="transition ease-out duration-150"
            enterFrom="opacity-0 translate-y-1 scale-95"
            enterTo="opacity-100 translate-y-0 scale-100"
            leave="transition ease-in duration-100"
            leaveFrom="opacity-100 translate-y-0 scale-100"
            leaveTo="opacity-0 translate-y-1 scale-95"
          >
            <Menu.Items className="absolute right-0 z-50 mt-2 w-48 origin-top-right rounded-lg border border-border bg-surface p-1 shadow-popover focus:outline-none">
              {actions.map((action) => (
                <Menu.Item key={action.label} disabled={action.disabled}>
                  {({ active, disabled }) => (
                    <button
                      type="button"
                      className={cn(
                        "flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm font-medium transition",
                        active && "bg-surface-muted",
                        action.danger ? "text-danger" : "text-text-primary",
                        disabled && "cursor-not-allowed opacity-45",
                      )}
                      onClick={action.onClick}
                      disabled={disabled}
                    >
                      <RiComputerLine className="h-4 w-4" aria-hidden />
                      {action.label}
                    </button>
                  )}
                </Menu.Item>
              ))}
            </Menu.Items>
          </Transition>
        </Menu>
      </div>
    </header>
  );
}

function formatStage(stage: string) {
  return stage
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
