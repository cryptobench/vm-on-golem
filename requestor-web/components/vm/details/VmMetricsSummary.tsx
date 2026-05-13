"use client";

import React from "react";
import { RiArrowDownLine, RiArrowUpLine } from "@remixicon/react";
import { Skeleton, SlidingSparkline } from "@golem/ui";
import type { VmMonitoringHistory } from "../../../lib/api";
import { DetailPanel, PanelTitle } from "./VmDetailPrimitives";
import {
  buildMetricChartRows,
  buildSparklineRows,
  formatMbps,
  formatPercent,
  latestNetworkRates,
} from "./metrics";

type GuestMetrics = Record<
  string,
  { value: number; unit: string; timestamp: string; source: string }
> | null;

const sparklineColors = {
  blue: "text-blue-500",
  violet: "text-violet-500",
  emerald: "text-emerald-500",
  cyan: "text-cyan-500",
  orange: "text-orange-500",
} as const;

export function VmMetricsSummary({
  guestMetrics,
  history,
  loading,
}: {
  guestMetrics: GuestMetrics;
  history?: VmMonitoringHistory;
  loading?: boolean;
}) {
  const rows = React.useMemo(
    () => buildMetricChartRows(history?.samples || []),
    [history],
  );
  const network = latestNetworkRates(rows);

  return (
    <DetailPanel className="vm-page-enter">
      <PanelTitle
        title="Live metrics"
        hint="Metrics are reported by the guest agent inside the VM."
      />

      {loading ? (
        <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-5">
          {Array.from({ length: 5 }).map((_, index) => (
            <Skeleton key={index} className="h-24 w-full" />
          ))}
        </div>
      ) : guestMetrics ? (
        <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-5">
          <MetricTile
            label="CPU"
            value={formatPercent(metricPercent(guestMetrics, "cpu_percent"))}
            values={buildSparklineRows(rows, "CPU")}
            color="blue"
          />
          <MetricTile
            label="Memory"
            value={formatPercent(metricPercent(guestMetrics, "memory_percent"))}
            values={buildSparklineRows(rows, "Memory")}
            color="violet"
          />
          <MetricTile
            label="Disk"
            value={formatPercent(metricPercent(guestMetrics, "disk_percent"))}
            values={buildSparklineRows(rows, "Disk")}
            color="emerald"
          />
          <NetworkRateTile
            label="Network In"
            value={network.rx}
            values={buildSparklineRows(rows, "Network RX")}
            direction="in"
          />
          <NetworkRateTile
            label="Network Out"
            value={network.tx}
            values={buildSparklineRows(rows, "Network TX")}
            direction="out"
          />
        </div>
      ) : (
        <div className="mt-4 rounded-md border border-warning bg-warning-soft p-4 text-sm text-text-primary">
          Guest metrics are not available yet. The default VM agent only
          publishes metrics and does not give providers shell or file access.
        </div>
      )}
    </DetailPanel>
  );
}

function MetricTile({
  label,
  value,
  values,
  color,
}: {
  label: string;
  value: string;
  values: ReturnType<typeof buildSparklineRows>;
  color: keyof typeof sparklineColors;
}) {
  return (
    <div className="vm-metric-tile rounded-lg border border-border bg-surface p-4">
      <div className="text-xs font-medium text-text-muted">{label}</div>
      <div className="mt-2 text-lg font-semibold text-text-primary">
        {value}
      </div>
      <MiniMetricChart values={values} color={color} />
    </div>
  );
}

function NetworkRateTile({
  label,
  value,
  values,
  direction,
}: {
  label: string;
  value: number | null;
  values: ReturnType<typeof buildSparklineRows>;
  direction: "in" | "out";
}) {
  const Icon = direction === "in" ? RiArrowDownLine : RiArrowUpLine;

  return (
    <div className="vm-metric-tile rounded-lg border border-border bg-surface p-4">
      <div className="flex items-center gap-2 text-xs font-medium text-text-muted">
        <Icon className="h-4 w-4" aria-hidden />
        {label}
      </div>
      <div className="mt-2 text-sm font-semibold text-text-primary">
        {formatMbps(value)}
      </div>
      <MiniMetricChart
        values={values}
        color={direction === "in" ? "cyan" : "orange"}
      />
    </div>
  );
}

function MiniMetricChart({
  values,
  color,
}: {
  values: ReturnType<typeof buildSparklineRows>;
  color: keyof typeof sparklineColors;
}) {
  if (values.length < 2) {
    return <div className="mt-2 h-9 rounded bg-surface-muted" />;
  }

  return (
    <SlidingSparkline
      className="mt-2 h-9"
      data={values}
      colorClassName={sparklineColors[color]}
      xKey="point"
      dataKey="value"
      animationKey={(row) => row.timestamp}
    />
  );
}

function metricPercent(guestMetrics: NonNullable<GuestMetrics>, name: string) {
  const value = Number(guestMetrics?.[name]?.value);
  if (!Number.isFinite(value)) return null;
  return Math.max(0, Math.min(100, value));
}
