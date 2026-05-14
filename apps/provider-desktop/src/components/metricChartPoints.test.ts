import assert from "node:assert/strict";
import test from "node:test";

import { metricChartPoints } from "./metricChartPoints";
import type { MetricsHistoryResponse } from "../lib/types";

test("metricChartPoints preserves all returned samples", () => {
  const history: MetricsHistoryResponse = {
    samples: Array.from({ length: 90 }, (_, index) => ({
      scope: "host",
      source: "infrastructure",
      metric: "cpu_percent",
      value: index,
      unit: "percent",
      timestamp: new Date(Date.UTC(2026, 4, 14, 19, index)).toISOString(),
      vm_id: null,
    })),
  };

  assert.equal(metricChartPoints(history, "cpu_percent").length, 90);
});
