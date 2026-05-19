import assert from "node:assert/strict";
import test from "node:test";

import {
  buildMetricChartRows,
  buildMetricChartRowsFromHistory,
  buildRoundedSparklineRows,
  getAppendOnlySlideChange,
  latestNetworkRates,
  networkTransferTotals,
} from "../components/vm/details/metrics";

test("reports latest network rates separately from transfer totals", () => {
  const samples = [
    networkSample("network_rx_bytes", 100_000_000, "2026-05-12T21:00:00+00:00"),
    networkSample("network_tx_bytes", 1_000_000, "2026-05-12T21:00:00+00:00"),
    networkSample("network_rx_bytes", 100_040_000, "2026-05-12T21:00:10+00:00"),
    networkSample("network_tx_bytes", 1_040_000, "2026-05-12T21:00:10+00:00"),
    networkSample("network_rx_bytes", 170_040_000, "2026-05-12T21:00:20+00:00"),
    networkSample("network_tx_bytes", 1_080_000, "2026-05-12T21:00:20+00:00"),
    networkSample("network_rx_bytes", 170_080_000, "2026-05-12T21:00:30+00:00"),
    networkSample("network_tx_bytes", 1_120_000, "2026-05-12T21:00:30+00:00"),
  ];
  const rows = buildMetricChartRows(samples);

  assert.deepEqual(latestNetworkRates(rows), {
    rx: 0.032,
    tx: 0.032,
  });
  assert.deepEqual(networkTransferTotals(samples), {
    rx: 70_080_000,
    tx: 120_000,
  });
});

test("builds metric rows from provider history points", () => {
  const rows = buildMetricChartRowsFromHistory({
    points: [
      historyPoint("cpu_percent", 12, "percent", "2026-05-12T21:00:00+00:00"),
      historyPoint(
        "memory_percent",
        34,
        "percent",
        "2026-05-12T21:00:00+00:00",
      ),
      historyPoint(
        "network_rx_bytes",
        100_000_000,
        "bytes",
        "2026-05-12T21:00:00+00:00",
      ),
      historyPoint("cpu_percent", 14, "percent", "2026-05-12T21:00:10+00:00"),
      historyPoint(
        "network_rx_bytes",
        100_040_000,
        "bytes",
        "2026-05-12T21:00:10+00:00",
      ),
    ],
  });

  assert.equal(rows[0].CPU, 12);
  assert.equal(rows[0].Memory, 34);
  assert.equal(rows[1].CPU, 14);
  assert.equal(rows[1]["Network RX"], 0.032);
});

test("builds live summary rows from raw live samples only", () => {
  const rows = buildMetricChartRows([
    metricSample("cpu_percent", 12, "percent", "2026-05-12T21:00:00+00:00"),
    metricSample("memory_percent", 34, "percent", "2026-05-12T21:00:00+00:00"),
    metricSample("network_rx_bytes", 100_000_000, "bytes", "2026-05-12T21:00:00+00:00"),
    metricSample("network_rx_bytes", 100_040_000, "bytes", "2026-05-12T21:00:10+00:00"),
  ]);

  assert.equal(rows[0].CPU, 12);
  assert.equal(rows[0].Memory, 34);
  assert.equal(rows[1]["Network RX"], 0.032);
});

test("rounds network sparklines to match displayed Mbps precision", () => {
  const rows = buildMetricChartRows([
    metricSample("network_rx_bytes", 100_000_000, "bytes", "2026-05-12T21:00:00+00:00"),
    metricSample("network_rx_bytes", 100_040_000, "bytes", "2026-05-12T21:00:10+00:00"),
    metricSample("network_rx_bytes", 100_100_000, "bytes", "2026-05-12T21:00:20+00:00"),
  ]);

  assert.deepEqual(
    buildRoundedSparklineRows(rows, "Network RX", 1).map((row) => row.value),
    [0, 0],
  );
});

test("detects appended metric timestamps for chart slides", () => {
  assert.deepEqual(
    getAppendOnlySlideChange(
      ["2026-05-12T21:00:00", "2026-05-12T21:00:10"],
      ["2026-05-12T21:00:00", "2026-05-12T21:00:10", "2026-05-12T21:00:20"],
    ),
    { appendedCount: 1, droppedCount: 0 },
  );
});

test("detects sliding-window metric timestamp appends", () => {
  assert.deepEqual(
    getAppendOnlySlideChange(
      [
        "2026-05-12T21:00:00",
        "2026-05-12T21:00:10",
        "2026-05-12T21:00:20",
        "2026-05-12T21:00:30",
      ],
      [
        "2026-05-12T21:00:10",
        "2026-05-12T21:00:20",
        "2026-05-12T21:00:30",
        "2026-05-12T21:00:40",
      ],
    ),
    { appendedCount: 1, droppedCount: 1 },
  );
});

test("does not slide on duplicate or reordered metric timestamps", () => {
  assert.equal(
    getAppendOnlySlideChange(
      ["2026-05-12T21:00:00", "2026-05-12T21:00:10"],
      ["2026-05-12T21:00:00", "2026-05-12T21:00:10", "2026-05-12T21:00:10"],
    ),
    null,
  );
  assert.equal(
    getAppendOnlySlideChange(
      ["2026-05-12T21:00:00", "2026-05-12T21:00:10", "2026-05-12T21:00:20"],
      [
        "2026-05-12T21:00:10",
        "2026-05-12T21:00:00",
        "2026-05-12T21:00:20",
        "2026-05-12T21:00:30",
      ],
    ),
    null,
  );
});

test("does not slide on metric range replacement", () => {
  assert.equal(
    getAppendOnlySlideChange(
      ["2026-05-12T21:00:00", "2026-05-12T21:00:10", "2026-05-12T21:00:20"],
      ["2026-05-12T22:00:00", "2026-05-12T22:00:10", "2026-05-12T22:00:20"],
    ),
    null,
  );
});

function networkSample(metric: string, value: number, timestamp: string) {
  return metricSample(metric, value, "bytes", timestamp);
}

function metricSample(
  metric: string,
  value: number,
  unit: string,
  timestamp: string,
) {
  return {
    scope: "vm",
    source: "guest_agent",
    metric,
    value,
    unit,
    timestamp,
    vm_id: "vm-ed1d",
  } as const;
}

function historyPoint(
  metric: string,
  avg: number,
  unit: string,
  bucketEnd: string,
) {
  return {
    scope: "vm",
    source: "guest_agent",
    metric,
    unit,
    avg,
    min: avg,
    max: avg,
    count: 1,
    bucket_start: bucketEnd,
    bucket_end: bucketEnd,
    vm_id: "vm-ed1d",
  } as const;
}
