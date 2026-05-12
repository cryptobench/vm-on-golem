"use client";

import React from "react";
import { LineChart } from "@tremor/react";
import {
  RiArrowDownLine,
  RiArrowUpLine,
  RiPulseLine,
} from "@remixicon/react";
import { Skeleton } from "../../ui/Skeleton";
import type { VmMonitoringHistory } from "../../../lib/api";
import { DetailPanel, PanelTitle } from "./VmDetailPrimitives";
import {
  buildMetricChartRows,
  buildSparklineValues,
  formatMbps,
  formatPercent,
  latestNetworkRates,
} from "./metrics";

type GuestMetrics = Record<
  string,
  { value: number; unit: string; timestamp: string; source: string }
> | null;

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
  const heartbeatSeconds = heartbeatAgeSeconds(guestMetrics?.agent_heartbeat?.timestamp);

  return (
    <DetailPanel className="vm-page-enter">
      <PanelTitle
        title="Latest guest metrics"
        hint="Metrics are reported by the guest agent inside the VM."
        trailing={
          <div className="text-xs text-text-secondary">
            <span>
              Agent heartbeat:{" "}
              {heartbeatSeconds == null ? "waiting" : `${heartbeatSeconds}s ago`}
            </span>
          </div>
        }
      />

      {loading ? (
        <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-24 w-full" />
          ))}
        </div>
      ) : guestMetrics ? (
        <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <MetricTile
            label="CPU"
            value={formatPercent(metricPercent(guestMetrics, "cpu_percent"))}
            values={buildSparklineValues(rows, "CPU")}
            color="blue"
          />
          <MetricTile
            label="Memory"
            value={formatPercent(metricPercent(guestMetrics, "memory_percent"))}
            values={buildSparklineValues(rows, "Memory")}
            color="violet"
          />
          <MetricTile
            label="Disk"
            value={formatPercent(metricPercent(guestMetrics, "disk_percent"))}
            values={buildSparklineValues(rows, "Disk")}
            color="emerald"
          />
          <NetworkTile rx={network.rx} tx={network.tx} />
        </div>
      ) : (
        <div className="mt-4 rounded-md border border-warning bg-warning-soft p-4 text-sm text-text-primary">
          Guest metrics are not available yet. The default VM agent only publishes
          metrics and does not give providers shell or file access.
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
  values: number[];
  color: "blue" | "violet" | "emerald";
}) {
  return (
    <div className="vm-metric-tile rounded-lg border border-border bg-surface p-4">
      <div className="text-xs font-medium text-text-muted">{label}</div>
      <div className="mt-2 text-lg font-semibold text-text-primary">{value}</div>
      <MiniMetricChart values={values} color={color} />
    </div>
  );
}

function NetworkTile({ rx, tx }: { rx: number | null; tx: number | null }) {
  return (
    <div className="vm-metric-tile rounded-lg border border-border bg-surface p-4">
      <div className="flex items-center gap-2 text-xs font-medium text-text-muted">
        <RiPulseLine className="h-4 w-4" aria-hidden />
        Network (1h)
      </div>
      <div className="mt-2 space-y-1 text-sm font-medium text-text-primary">
        <div className="flex items-center gap-1">
          <RiArrowDownLine className="h-4 w-4 text-text-secondary" aria-hidden />
          {formatMbps(rx)}
        </div>
        <div className="flex items-center gap-1">
          <RiArrowUpLine className="h-4 w-4 text-text-secondary" aria-hidden />
          {formatMbps(tx)}
        </div>
      </div>
    </div>
  );
}

function MiniMetricChart({
  values,
  color,
}: {
  values: number[];
  color: "blue" | "violet" | "emerald";
}) {
  const data = React.useMemo(
    () =>
      values.slice(-24).map((value, index) => ({
        point: String(index + 1),
        value,
      })),
    [values],
  );

  if (data.length < 2) {
    return <div className="mt-2 h-9 rounded bg-surface-muted" />;
  }

  return (
    <LineChart
      className="mt-2 h-9"
      data={data}
      index="point"
      categories={["value"]}
      colors={[color]}
      showXAxis={false}
      showYAxis={false}
      showLegend={false}
      showGridLines={false}
      showTooltip={false}
      autoMinValue
      showAnimation
    />
  );
}

function metricPercent(guestMetrics: NonNullable<GuestMetrics>, name: string) {
  const value = Number(guestMetrics?.[name]?.value);
  if (!Number.isFinite(value)) return null;
  return Math.max(0, Math.min(100, value));
}

function heartbeatAgeSeconds(timestamp?: string) {
  if (!timestamp) return null;
  const age = Math.max(0, Date.now() - Date.parse(timestamp));
  if (!Number.isFinite(age)) return null;
  return Math.floor(age / 1000);
}
