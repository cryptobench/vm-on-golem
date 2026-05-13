"use client";

import React from "react";
import { Skeleton } from "../ui/Skeleton";
import type { VmMonitoringHistory } from "../../lib/api";
import { DetailPanel, PanelTitle } from "./details/VmDetailPrimitives";
import {
  buildMetricChartRows,
  formatChartPercent,
  metricRanges,
  type MetricRange,
} from "./details/metrics";
import { cn } from "../ui/cn";
import { SlidingMetricLineChart } from "./details/SlidingMetricCharts";

type VmMetricsChartsProps = {
  history?: VmMonitoringHistory;
  loading?: boolean;
  range: MetricRange;
  onRangeChange: (range: MetricRange) => void;
};

export function VmMetricsCharts({
  history,
  loading,
  range,
  onRangeChange,
}: VmMetricsChartsProps) {
  const chartRows = React.useMemo(
    () => buildMetricChartRows(history?.samples || []),
    [history],
  );
  const hasData = chartRows.some((row) =>
    ["CPU", "Memory", "Disk", "Network RX", "Network TX"].some(
      (key) => typeof row[key as keyof typeof row] === "number",
    ),
  );

  return (
    <DetailPanel className="vm-page-enter">
      <PanelTitle
        title="Historical metrics"
        hint="Percent series use the left scale. Network series are normalized to Mbps for trend comparison."
        trailing={
          <div className="inline-grid h-9 grid-cols-4 overflow-hidden rounded-md border border-border bg-surface">
            {metricRanges.map((item) => (
              <button
                key={item.value}
                type="button"
                className={cn(
                  "min-w-12 px-4 text-sm font-medium transition",
                  range === item.value
                    ? "bg-primary text-white"
                    : "text-text-secondary hover:bg-surface-muted hover:text-text-primary",
                )}
                onClick={() => onRangeChange(item.value)}
              >
                {item.label}
              </button>
            ))}
          </div>
        }
      />

      {loading ? (
        <Skeleton className="mt-5 h-80 w-full" />
      ) : hasData ? (
        <div className="mt-5 h-80">
          <SlidingMetricLineChart
            className="h-80"
            data={chartRows}
            categories={["CPU", "Memory", "Disk", "Network RX", "Network TX"]}
            valueFormatter={formatChartPercent}
            yAxisWidth={56}
            minValue={0}
          />
        </div>
      ) : (
        <div className="mt-5 flex h-80 items-center justify-center rounded-lg border border-dashed border-border bg-surface-muted text-sm text-text-secondary">
          Waiting for enough metric samples.
        </div>
      )}
    </DetailPanel>
  );
}
