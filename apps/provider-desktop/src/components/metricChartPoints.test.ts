import assert from "node:assert/strict";
import test from "node:test";

import { metricChartPoints } from "./metricChartPoints";
import type { MetricsHistoryResponse } from "../lib/types";

test("metricChartPoints maps aggregated history points", () => {
  const history: MetricsHistoryResponse = {
    range: "7d",
    resolution_seconds: 3600,
    generated_at: "2026-05-14T19:00:00.000Z",
    points: Array.from({ length: 90 }, (_, index) => ({
      scope: "host",
      source: "infrastructure",
      metric: "cpu_percent",
      unit: "percent",
      vm_id: null,
      bucket_start: new Date(Date.UTC(2026, 4, 14, index)).toISOString(),
      bucket_end: new Date(Date.UTC(2026, 4, 14, index + 1)).toISOString(),
      avg: index + 0.123,
      min: index,
      max: index + 1,
      count: 3,
    })),
  };

  const points = metricChartPoints(history, "cpu_percent");
  assert.equal(points.length, 90);
  assert.deepEqual(points[0], {
    timestamp: Date.UTC(2026, 4, 14, 0),
    bucketStart: Date.UTC(2026, 4, 14, 0),
    bucketEnd: Date.UTC(2026, 4, 14, 1),
    value: 0.12,
    min: 0,
    max: 1,
    count: 3,
  });
});
