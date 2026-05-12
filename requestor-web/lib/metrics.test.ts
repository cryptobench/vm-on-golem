import assert from "node:assert/strict";
import test from "node:test";

import {
  buildMetricChartRows,
  latestNetworkRates,
  networkTransferTotals,
} from "../components/vm/details/metrics";

test("reports latest network rates separately from transfer totals", () => {
  const samples = [
    networkSample("network_rx_bytes", 100_000_000, "2026-05-12T21:00:00"),
    networkSample("network_tx_bytes", 1_000_000, "2026-05-12T21:00:00"),
    networkSample("network_rx_bytes", 100_040_000, "2026-05-12T21:00:10"),
    networkSample("network_tx_bytes", 1_040_000, "2026-05-12T21:00:10"),
    networkSample("network_rx_bytes", 170_040_000, "2026-05-12T21:00:20"),
    networkSample("network_tx_bytes", 1_080_000, "2026-05-12T21:00:20"),
    networkSample("network_rx_bytes", 170_080_000, "2026-05-12T21:00:30"),
    networkSample("network_tx_bytes", 1_120_000, "2026-05-12T21:00:30"),
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
