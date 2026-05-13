"use client";

import React from "react";
import Link from "next/link";
import { RiExternalLinkLine } from "@remixicon/react";
import { vmDetailsHref } from "../../lib/routes";
import { CopyValue } from "../rentals/CopyValue";
import { Button } from "../ui/Button";
import { CurrencyCell } from "./CurrencyCell";
import { StreamRunway } from "./StreamRunway";
import { StreamTopUpModal } from "./StreamTopUpModal";
import { VmActivity } from "./StreamStatusPill";
import {
  type DisplayCurrency,
  hourlyTokenRate,
  remainingTokenBalance,
  spentTokenBalance,
  streamStatus,
  type StreamRow,
} from "./streamModel";

type StreamTableRowProps = {
  row: StreamRow;
  nowSec: number;
  busy: boolean;
  actionsDisabled: boolean;
  actionsDisabledReason?: string | null;
  displayCurrency: DisplayCurrency;
  onTopUp: (seconds: number) => void;
};

export function StreamTableRow({
  row,
  nowSec,
  busy,
  actionsDisabled,
  actionsDisabledReason,
  displayCurrency,
  onTopUp,
}: StreamTableRowProps) {
  const [topUpOpen, setTopUpOpen] = React.useState(false);
  const status = streamStatus(row, nowSec);
  const tokenRate = hourlyTokenRate(row);
  const spent = spentTokenBalance(row, nowSec);
  const balance = remainingTokenBalance(row, nowSec);
  const hourlyUsd = row.usdPrice == null ? null : tokenRate * row.usdPrice;
  const terminal = row.chain.halted || status === "out-of-funds";

  return (
    <tr className="streams-table-row border-t border-border first:border-t-0">
      <td className="td whitespace-nowrap py-5">
        <Link
          className="font-semibold text-text-primary transition hover:text-primary"
          href={vmDetailsHref(row.r.vm_id)}
        >
          {row.r.name || row.r.vm_id}
        </Link>
        <div className="mt-2">
          <VmActivity status={row.r.status} />
        </div>
      </td>
      <td className="td whitespace-nowrap py-5">
        <StreamRunway row={row} nowSec={nowSec} />
      </td>
      <td className="td whitespace-nowrap py-5">
        <CurrencyCell
          amount={spent}
          displayCurrency={displayCurrency}
          row={row}
        />
      </td>
      <td className="td whitespace-nowrap py-5">
        <CurrencyCell
          amount={balance}
          displayCurrency={displayCurrency}
          row={row}
        />
      </td>
      <td className="td whitespace-nowrap py-5">
        <CurrencyCell
          amount={tokenRate}
          displayCurrency={displayCurrency}
          fiatAmount={hourlyUsd}
          row={row}
          tokenLabelSuffix="/h"
        />
      </td>
      <td className="td whitespace-nowrap py-5">
        <span className="inline-flex items-center gap-2 font-medium">
          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary text-xs font-semibold text-white">
            {(row.tokenSymbol || "T").slice(0, 1)}
          </span>
          {row.tokenSymbol || "TOKEN"}
        </span>
      </td>
      <td className="td whitespace-nowrap py-5">
        <CopyValue value={row.chain.recipient || row.r.provider_id} />
      </td>
      <td className="td whitespace-nowrap py-5">
        <CopyValue value={row.r.stream_id} />
      </td>
      <td className="td whitespace-nowrap py-5 text-right">
        {terminal ? (
          <Link
            className="inline-flex h-9 items-center gap-2 rounded-md px-3 text-sm font-medium text-primary transition hover:bg-surface-muted"
            href={vmDetailsHref(row.r.vm_id)}
          >
            Details
            <RiExternalLinkLine className="h-4 w-4" aria-hidden />
          </Link>
        ) : (
          <>
            <Button
              className="px-3 text-primary ring-border"
              disabled={busy || actionsDisabled}
              onClick={() => setTopUpOpen(true)}
              title={actionsDisabledReason || undefined}
              variant="secondary"
            >
              Top up
            </Button>
            <StreamTopUpModal
              busy={busy}
              disabled={actionsDisabled}
              disabledReason={actionsDisabledReason}
              onClose={() => setTopUpOpen(false)}
              onTopUp={(seconds) => onTopUp(seconds)}
              open={topUpOpen}
              row={row}
            />
          </>
        )}
      </td>
    </tr>
  );
}
