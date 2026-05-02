"use client";

import React from "react";
import { LineChart } from "@tremor/react";
import { Skeleton } from "../ui/Skeleton";
import type { VmMonitoringHistory } from "../../lib/api";

type MetricRange = "1h" | "6h" | "24h" | "7d";

type VmMetricsChartsProps = {
  history?: VmMonitoringHistory;
  loading?: boolean;
  range: MetricRange;
  onRangeChange: (range: MetricRange) => void;
};

const ranges: Array<{ value: MetricRange; label: string }> = [
  { value: "1h", label: "1H" },
  { value: "6h", label: "6H" },
  { value: "24h", label: "24H" },
  { value: "7d", label: "7D" },
];

export function VmMetricsCharts({
  history,
  loading,
  range,
  onRangeChange,
}: VmMetricsChartsProps) {
  const samples = history?.samples || [];
  const usageData = React.useMemo(
    () => percentSeries(samples, ["cpu_percent", "memory_percent", "disk_percent"]),
    [samples],
  );
  const networkData = React.useMemo(
    () => rateSeries(samples, ["network_rx_bytes", "network_tx_bytes"]),
    [samples],
  );
  const hasUsageData = usageData.some((row) =>
    ["CPU", "RAM", "Disk"].some((key) => typeof row[key] === "number"),
  );
  const hasNetworkData = networkData.some((row) =>
    ["RX", "TX"].some((key) => typeof row[key] === "number"),
  );

  return (
    <div className="card">
      <div className="card-body">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h3>Usage Charts</h3>
            <div className="text-sm text-gray-500">Guest-reported CPU, memory, disk, and network activity.</div>
          </div>
          <div className="inline-flex h-10 items-center border border-gray-200 bg-white">
            {ranges.map((item) => (
              <button
                key={item.value}
                type="button"
                className={`h-full px-3 text-sm font-medium ${range === item.value ? "bg-brand-600 text-white" : "text-gray-700 hover:bg-gray-50"}`}
                onClick={() => onRangeChange(item.value)}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>

        {loading ? (
          <div className="mt-5 grid gap-5 lg:grid-cols-2">
            <Skeleton className="h-72 w-full" />
            <Skeleton className="h-72 w-full" />
          </div>
        ) : (
          <div className="mt-5 grid gap-5 lg:grid-cols-2">
            <ChartPanel title="CPU, RAM, Disk" empty={!hasUsageData}>
              <LineChart
                className="h-64"
                data={usageData}
                index="time"
                categories={["CPU", "RAM", "Disk"]}
                colors={["blue", "emerald", "amber"]}
                valueFormatter={(value) => `${value.toFixed(0)}%`}
                yAxisWidth={42}
                minValue={0}
                maxValue={100}
                showAnimation={false}
              />
            </ChartPanel>
            <ChartPanel title="Network" empty={!hasNetworkData}>
              <LineChart
                className="h-64"
                data={networkData}
                index="time"
                categories={["RX", "TX"]}
                colors={["cyan", "violet"]}
                valueFormatter={(value) => formatRate(value)}
                yAxisWidth={62}
                showAnimation={false}
              />
            </ChartPanel>
          </div>
        )}
      </div>
    </div>
  );
}

function ChartPanel({
  title,
  empty,
  children,
}: {
  title: string;
  empty: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="border border-gray-200 p-4">
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm font-medium text-gray-900">{title}</div>
      </div>
      {empty ? (
        <div className="mt-4 flex h-64 items-center justify-center border border-dashed border-gray-200 text-sm text-gray-500">
          Waiting for enough metric samples.
        </div>
      ) : (
        <div className="mt-4">{children}</div>
      )}
    </div>
  );
}

function percentSeries(samples: VmMonitoringHistory["samples"], metrics: string[]) {
  const labels: Record<string, string> = {
    cpu_percent: "CPU",
    memory_percent: "RAM",
    disk_percent: "Disk",
  };
  const rows = new Map<string, Record<string, string | number>>();
  samples
    .filter((sample) => sample.source === "guest_agent" && metrics.includes(sample.metric))
    .sort((a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp))
    .forEach((sample) => {
      const time = formatTime(sample.timestamp);
      const row = rows.get(sample.timestamp) || { time };
      row[labels[sample.metric]] = clampPercent(sample.value);
      rows.set(sample.timestamp, row);
    });
  return Array.from(rows.values());
}

function rateSeries(samples: VmMonitoringHistory["samples"], metrics: string[]) {
  const labels: Record<string, string> = {
    network_rx_bytes: "RX",
    network_tx_bytes: "TX",
  };
  const previous = new Map<string, { timestamp: number; value: number }>();
  const rows = new Map<string, Record<string, string | number>>();
  samples
    .filter((sample) => sample.source === "guest_agent" && metrics.includes(sample.metric))
    .sort((a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp))
    .forEach((sample) => {
      const timestamp = Date.parse(sample.timestamp);
      const last = previous.get(sample.metric);
      previous.set(sample.metric, { timestamp, value: sample.value });
      if (!last) return;
      const seconds = Math.max(1, (timestamp - last.timestamp) / 1000);
      const delta = Math.max(0, sample.value - last.value);
      const row = rows.get(sample.timestamp) || { time: formatTime(sample.timestamp) };
      row[labels[sample.metric]] = delta / seconds;
      rows.set(sample.timestamp, row);
    });
  return Array.from(rows.values());
}

function clampPercent(value: number) {
  return Math.max(0, Math.min(100, value));
}

function formatRate(bytesPerSecond: number) {
  if (bytesPerSecond >= 1024 * 1024) return `${(bytesPerSecond / 1024 / 1024).toFixed(1)} MB/s`;
  if (bytesPerSecond >= 1024) return `${(bytesPerSecond / 1024).toFixed(1)} KB/s`;
  return `${bytesPerSecond.toFixed(0)} B/s`;
}

function formatTime(timestamp: string) {
  return new Date(timestamp).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}
