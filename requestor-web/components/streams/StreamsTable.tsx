"use client";

import React from "react";
import { StreamTableRow } from "./StreamTableRow";
import { StreamTableTabs } from "./StreamTableTabs";
import {
  type DisplayCurrency,
  sortRowsByImportance,
  type StreamRow,
} from "./streamModel";

type StreamView = "active" | "ended";

type StreamsTableProps = {
  active: StreamRow[];
  ended: StreamRow[];
  nowSec: number;
  showEnded: boolean;
  onShowEndedChange: (value: boolean) => void;
  busy: Record<string, boolean>;
  actionsDisabled: boolean;
  actionsDisabledReason?: string | null;
  displayCurrency: DisplayCurrency;
  onTopUp: (row: StreamRow, seconds: number) => void;
};

const STREAM_HEADERS = [
  "VM",
  "Remaining Time",
  "Spent So Far",
  "Remaining Balance",
  "Hourly Rate",
  "Token",
  "Provider",
  "Stream ID",
  "Actions",
];

export function StreamsTable({
  active,
  ended,
  nowSec,
  showEnded,
  onShowEndedChange,
  busy,
  actionsDisabled,
  actionsDisabledReason,
  displayCurrency,
  onTopUp,
}: StreamsTableProps) {
  const [view, setView] = React.useState<StreamView>(
    showEnded && ended.length ? "ended" : "active",
  );
  const previousShowEnded = React.useRef(showEnded);
  const rows = React.useMemo(
    () => sortRowsByImportance(view === "ended" ? ended : active, nowSec),
    [active, ended, nowSec, view],
  );

  React.useEffect(() => {
    const wasShowingEnded = previousShowEnded.current;
    previousShowEnded.current = showEnded;

    if (!showEnded) {
      setView("active");
      return;
    }

    if (!wasShowingEnded && ended.length) {
      setView("ended");
    }
  }, [ended.length, showEnded]);

  React.useEffect(() => {
    if (view === "ended" && (!showEnded || !ended.length)) {
      setView("active");
    }
  }, [ended.length, showEnded, view]);

  const toggleShowEnded = () => {
    const next = !showEnded;
    onShowEndedChange(next);
    setView(next && ended.length ? "ended" : "active");
  };

  return (
    <section className="streams-table-shell overflow-hidden rounded-lg border border-border bg-surface shadow-soft">
      <StreamTableTabs
        activeCount={active.length}
        endedCount={ended.length}
        onShowEndedToggle={toggleShowEnded}
        onViewChange={setView}
        showEnded={showEnded}
        view={view}
      />
      <div className="overflow-x-auto">
        <table className="table min-w-full">
          <thead className="bg-surface">
            <tr>
              {STREAM_HEADERS.map((header) => (
                <th
                  className="th whitespace-nowrap py-4 normal-case tracking-normal"
                  key={header}
                >
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <StreamTableRow
                actionsDisabled={actionsDisabled}
                actionsDisabledReason={actionsDisabledReason}
                busy={!!busy[String(row.r.stream_id)]}
                displayCurrency={displayCurrency}
                key={`${row.r.vm_id}-${row.r.stream_id}`}
                nowSec={nowSec}
                onTopUp={(seconds) => onTopUp(row, seconds)}
                row={row}
              />
            ))}
          </tbody>
        </table>
      </div>
      <div className="border-t border-border px-5 py-4 text-sm text-text-secondary">
        Showing {rows.length} of {active.length + ended.length} stream
        {active.length + ended.length === 1 ? "" : "s"}
      </div>
    </section>
  );
}
