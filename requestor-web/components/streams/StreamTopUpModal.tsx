"use client";

import React from "react";
import { RiCloseLine, RiTimeLine } from "@remixicon/react";
import { humanDuration } from "../../lib/streams";
import { parseHumanDuration } from "../../lib/time";
import { Button } from "@golem/ui";
import { Callout } from "@golem/ui";
import { Modal } from "@golem/ui";
import { SelectableCard } from "@golem/ui";
import { formatTokenValue } from "./CurrencyCell";
import {
  formatFiat,
  hourlyTokenRate,
  type StreamRow,
} from "./streamModel";

const TOP_UP_PRESETS = [
  { label: "30 min", seconds: 1800 },
  { label: "1 hour", seconds: 3600 },
  { label: "2 hours", seconds: 7200 },
  { label: "6 hours", seconds: 21600 },
];

type StreamTopUpModalProps = {
  open: boolean;
  row: StreamRow;
  busy: boolean;
  disabled: boolean;
  disabledReason?: string | null;
  onClose: () => void;
  onTopUp: (seconds: number) => void;
};

export function StreamTopUpModal({
  open,
  row,
  busy,
  disabled,
  disabledReason,
  onClose,
  onTopUp,
}: StreamTopUpModalProps) {
  const [selectedSeconds, setSelectedSeconds] = React.useState(3600);
  const [custom, setCustom] = React.useState("");
  const customSeconds = parseHumanDuration(custom);
  const usingCustom = custom.trim().length > 0;
  const topUpSeconds = usingCustom ? customSeconds : selectedSeconds;
  const blocked = disabled || (usingCustom && customSeconds <= 0);
  const buttonTitle =
    disabledReason ||
    (usingCustom && customSeconds <= 0 ? "Enter a valid duration." : undefined);
  const tokenRate = hourlyTokenRate(row);
  const topUpToken = (tokenRate / 3600) * Math.max(0, topUpSeconds);
  const topUpFiat = row.usdPrice == null ? null : topUpToken * row.usdPrice;

  React.useEffect(() => {
    if (!open) {
      setSelectedSeconds(3600);
      setCustom("");
    }
  }, [open]);

  const submit = () => {
    if (blocked || busy || topUpSeconds <= 0) return;
    onTopUp(topUpSeconds);
  };

  return (
    <Modal open={open} onClose={busy ? () => undefined : onClose} size="lg">
      <div className="p-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-text-primary">
              Top up stream
            </h2>
            <p className="mt-3 text-sm leading-5 text-text-secondary">
              Select how much runway to add to {row.r.name || row.r.vm_id}.
            </p>
          </div>
          <button
            aria-label="Close top-up dialog"
            className="inline-flex h-8 w-8 items-center justify-center rounded-md text-text-muted transition hover:bg-surface-muted hover:text-text-primary"
            disabled={busy}
            onClick={onClose}
            type="button"
          >
            <RiCloseLine className="h-5 w-5" aria-hidden />
          </button>
        </div>

        <div className="mt-6 grid gap-2 sm:grid-cols-4">
          {TOP_UP_PRESETS.map((preset) => (
            <SelectableCard
              className="min-h-16 px-3 py-2"
              key={preset.seconds}
              onClick={() => {
                if (busy) return;
                setCustom("");
                setSelectedSeconds(preset.seconds);
              }}
              selected={!usingCustom && selectedSeconds === preset.seconds}
            >
              <span className="text-sm font-semibold text-text-primary">
                {preset.label}
              </span>
              <span className="mt-1 text-xs text-text-secondary">
                {humanDuration(preset.seconds)}
              </span>
            </SelectableCard>
          ))}
        </div>

        <label className="label mt-5">Custom duration</label>
        <div className="relative mt-2">
          <input
            className="input h-10 pr-10"
            disabled={busy}
            onChange={(event) => setCustom(event.target.value)}
            placeholder="45m, 1h, 2d"
            value={custom}
          />
          <RiTimeLine
            aria-hidden
            className="absolute right-3 top-3 h-4 w-4 text-text-muted"
          />
        </div>
        {usingCustom && customSeconds <= 0 ? (
          <div className="mt-2 text-sm text-danger">Enter a valid duration.</div>
        ) : null}

        <Callout className="mt-5">
          Adds {humanDuration(Math.max(0, topUpSeconds))} for about{" "}
          {formatTokenValue(topUpToken, row.tokenSymbol)}
          {topUpFiat == null ? "" : ` (${formatFiat(topUpFiat, 2)})`}.
        </Callout>

        {disabledReason ? (
          <Callout tone="warning" className="mt-4">
            {disabledReason}
          </Callout>
        ) : null}

        <div className="mt-5 flex justify-end gap-3">
          <Button
            className="px-6"
            disabled={busy}
            onClick={onClose}
            variant="secondary"
          >
            Cancel
          </Button>
          <Button
            busy={busy}
            className="min-w-40 px-6"
            disabled={blocked}
            onClick={submit}
            title={buttonTitle}
            variant="primary"
          >
            {busy ? "Sending" : "Top up"}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
