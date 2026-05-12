"use client";

import React from "react";
import { Menu, Transition } from "@headlessui/react";
import { RiArrowDownSLine } from "@remixicon/react";
import { parseHumanDuration } from "../../lib/time";
import { cn } from "../ui/cn";
import { Spinner } from "../ui/Spinner";

type StreamTopUpControlsProps = {
  busy: boolean;
  disabled: boolean;
  disabledReason?: string | null;
  onTopUp: (seconds: number) => void;
};

const PRESETS = [
  { label: "+30 min", seconds: 1800 },
  { label: "+1 h", seconds: 3600 },
  { label: "+2 h", seconds: 7200 },
];

export function StreamTopUpControls({
  busy,
  disabled,
  disabledReason,
  onTopUp,
}: StreamTopUpControlsProps) {
  const [custom, setCustom] = React.useState("");
  const [lastAction, setLastAction] = React.useState<number | "custom" | null>(null);
  const topUpDisabled = busy || disabled;
  const customSeconds = parseHumanDuration(custom);

  React.useEffect(() => {
    if (!busy) setLastAction(null);
  }, [busy]);

  const run = (seconds: number, action: number | "custom") => {
    setLastAction(action);
    onTopUp(seconds);
  };

  return (
    <div className="flex items-center justify-end gap-1" title={disabledReason || undefined}>
      <button
        className="btn btn-secondary h-9 px-3 text-primary ring-border"
        disabled={topUpDisabled}
        onClick={() => run(3600, 3600)}
        type="button"
      >
        {busy && lastAction === 3600 ? <Spinner className="h-4 w-4" /> : "Top up"}
      </button>
      <Menu as="div" className="relative">
        <Menu.Button
          className="btn btn-secondary h-9 w-9 px-0 text-primary ring-border"
          disabled={topUpDisabled}
          aria-label="Choose top-up duration"
        >
          <RiArrowDownSLine className="h-5 w-5" aria-hidden />
        </Menu.Button>
        <Transition
          as={React.Fragment}
          enter="transition ease-out duration-100"
          enterFrom="opacity-0 -translate-y-1 scale-95"
          enterTo="opacity-100 translate-y-0 scale-100"
          leave="transition ease-in duration-75"
          leaveFrom="opacity-100 translate-y-0 scale-100"
          leaveTo="opacity-0 -translate-y-1 scale-95"
        >
          <Menu.Items className="streams-action-menu absolute right-0 z-20 mt-2 w-56 rounded-lg border border-border bg-surface p-2 shadow-popover focus:outline-none">
            {PRESETS.map((preset) => (
              <Menu.Item key={preset.seconds}>
                {({ active }) => (
                  <button
                    className={cn(
                      "flex h-9 w-full items-center rounded-md px-3 text-left text-sm text-text-secondary",
                      active && "bg-surface-muted text-text-primary",
                    )}
                    onClick={() => run(preset.seconds, preset.seconds)}
                    type="button"
                  >
                    {busy && lastAction === preset.seconds ? (
                      <Spinner className="mr-2 h-4 w-4" />
                    ) : null}
                    {preset.label}
                  </button>
                )}
              </Menu.Item>
            ))}
            <div className="mt-2 border-t border-border pt-2">
              <label className="text-xs font-medium text-text-secondary">Custom duration</label>
              <div className="mt-2 flex gap-2">
                <input
                  className="input h-9 text-sm"
                  placeholder="45m, 1h30m"
                  value={custom}
                  onChange={(event) => setCustom(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key !== "Enter" || !customSeconds) return;
                    event.preventDefault();
                    run(customSeconds, "custom");
                  }}
                />
                <button
                  className="btn btn-secondary h-9 px-3"
                  disabled={!customSeconds}
                  onClick={() => customSeconds && run(customSeconds, "custom")}
                  type="button"
                >
                  {busy && lastAction === "custom" ? <Spinner className="h-4 w-4" /> : "Apply"}
                </button>
              </div>
            </div>
          </Menu.Items>
        </Transition>
      </Menu>
    </div>
  );
}
