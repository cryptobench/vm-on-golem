import type { VmMonitoringHistory } from "../../../lib/api";
export { getAppendOnlySlideChange } from "@golem/ui";

export type MetricRange = "1h" | "6h" | "24h" | "7d";

export type MetricSeriesKey = "cpu" | "memory" | "disk" | "rx" | "tx";

export type MetricChartRow = {
  timestamp: string;
  time: string;
  CPU?: number;
  Memory?: number;
  Disk?: number;
  "Network RX"?: number;
  "Network TX"?: number;
};

type MetricValueKey = Exclude<keyof MetricChartRow, "timestamp" | "time">;

export type MetricSparklineRow = {
  timestamp: string;
  point: string;
  value: number;
};

export const metricRanges: Array<{ value: MetricRange; label: string }> = [
  { value: "1h", label: "1H" },
  { value: "6h", label: "6H" },
  { value: "24h", label: "24H" },
  { value: "7d", label: "7D" },
];

const percentMetricLabels: Record<string, MetricValueKey> = {
  cpu_percent: "CPU",
  memory_percent: "Memory",
  disk_percent: "Disk",
};

const networkMetricLabels: Record<string, MetricValueKey> = {
  network_rx_bytes: "Network RX",
  network_tx_bytes: "Network TX",
};

export function buildMetricChartRows(
  samples: VmMonitoringHistory["samples"] = [],
) {
  const rows = new Map<string, MetricChartRow>();
  const previousCounters = new Map<
    string,
    { timestamp: number; value: number }
  >();

  sortedGuestSamples(samples).forEach((sample) => {
    const row = rows.get(sample.timestamp) || {
      timestamp: sample.timestamp,
      time: formatChartTime(sample.timestamp),
    };

    if (sample.metric in percentMetricLabels) {
      row[percentMetricLabels[sample.metric]] = clampPercent(sample.value);
      rows.set(sample.timestamp, row);
      return;
    }

    if (sample.metric in networkMetricLabels) {
      const timestamp = parseMetricTimestamp(sample.timestamp);
      const previous = previousCounters.get(sample.metric);
      previousCounters.set(sample.metric, { timestamp, value: sample.value });
      if (!previous) return;

      const seconds = Math.max(1, (timestamp - previous.timestamp) / 1000);
      const delta = Math.max(0, sample.value - previous.value);
      row[networkMetricLabels[sample.metric]] = bytesToMbps(delta / seconds);
      rows.set(sample.timestamp, row);
    }
  });

  return Array.from(rows.values()).sort(
    (a, b) =>
      parseMetricTimestamp(a.timestamp) - parseMetricTimestamp(b.timestamp),
  );
}

export function buildSparklineValues(
  rows: MetricChartRow[],
  key: MetricValueKey,
) {
  return rows
    .map((row) => row[key])
    .filter(
      (value): value is number =>
        typeof value === "number" && Number.isFinite(value),
    );
}

export function buildSparklineRows(
  rows: MetricChartRow[],
  key: MetricValueKey,
): MetricSparklineRow[] {
  return rows
    .filter(
      (row) =>
        typeof row[key] === "number" && Number.isFinite(row[key] as number),
    )
    .slice(-24)
    .map((row, index) => ({
      timestamp: row.timestamp,
      point: String(index + 1),
      value: row[key] as number,
    }));
}

export function latestNetworkRates(rows: MetricChartRow[]) {
  const latest = [...rows]
    .reverse()
    .find(
      (row) =>
        typeof row["Network RX"] === "number" ||
        typeof row["Network TX"] === "number",
    );

  return {
    rx:
      typeof latest?.["Network RX"] === "number" ? latest["Network RX"] : null,
    tx:
      typeof latest?.["Network TX"] === "number" ? latest["Network TX"] : null,
  };
}

export function networkTransferTotals(
  samples: VmMonitoringHistory["samples"] = [],
) {
  const previousCounters = new Map<string, number>();
  const totals = {
    rx: 0,
    tx: 0,
  };
  const hasDelta = {
    rx: false,
    tx: false,
  };

  sortedGuestSamples(samples).forEach((sample) => {
    if (!(sample.metric in networkMetricLabels)) return;

    const previous = previousCounters.get(sample.metric);
    previousCounters.set(sample.metric, sample.value);
    if (previous == null) return;

    const delta = Math.max(0, sample.value - previous);
    if (sample.metric === "network_rx_bytes") {
      totals.rx += delta;
      hasDelta.rx = true;
    }
    if (sample.metric === "network_tx_bytes") {
      totals.tx += delta;
      hasDelta.tx = true;
    }
  });

  return {
    rx: hasDelta.rx ? totals.rx : null,
    tx: hasDelta.tx ? totals.tx : null,
  };
}

export function formatPercent(value: number | null) {
  return value == null ? "-" : `${value.toFixed(0)}%`;
}

export function formatMbps(value: number | null) {
  return value == null ? "-" : `${value.toFixed(1)} Mbps`;
}

export function formatBytes(value: number | null) {
  if (value == null) return "-";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let scaled = value;
  let unitIndex = 0;
  while (scaled >= 1000 && unitIndex < units.length - 1) {
    scaled /= 1000;
    unitIndex += 1;
  }
  return `${scaled.toFixed(unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}

export function formatChartPercent(value: number) {
  return `${value.toFixed(0)}%`;
}

export function formatChartMbps(value: number) {
  return `${value.toFixed(1)} Mbps`;
}

export function clampPercent(value: number) {
  return Math.max(0, Math.min(100, value));
}

function sortedGuestSamples(samples: VmMonitoringHistory["samples"]) {
  return samples
    .filter((sample) => sample.source === "guest_agent")
    .sort(
      (a, b) =>
        parseMetricTimestamp(a.timestamp) - parseMetricTimestamp(b.timestamp),
    );
}

function bytesToMbps(bytesPerSecond: number) {
  return (bytesPerSecond * 8) / 1_000_000;
}

function formatChartTime(timestamp: string) {
  return new Date(parseMetricTimestamp(timestamp)).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function parseMetricTimestamp(timestamp: string) {
  const normalized = hasTimezone(timestamp) ? timestamp : `${timestamp}Z`;
  return Date.parse(normalized);
}

function hasTimezone(timestamp: string) {
  return /(?:Z|[+-]\d{2}:?\d{2})$/i.test(timestamp);
}
