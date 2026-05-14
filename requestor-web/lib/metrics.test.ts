import assert from "node:assert/strict";
import test from "node:test";

import {
  buildMetricChartRows,
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
  return {
    scope: "vm",
    source: "guest_agent",
    metric,
    value,
    unit: "bytes",
    timestamp,
    vm_id: "vm-ed1d",
  } as const;
}
