import { parseAbsoluteTimestamp, type TimeSeriesPoint } from "@golem/ui";
import type { MetricsHistoryResponse } from "../lib/types";

export function metricChartPoints(
  history: MetricsHistoryResponse | null | undefined,
  metric: string,
): TimeSeriesPoint[] {
  const points = history?.points ?? [];
  return points
    .filter((point) => point.metric === metric)
    .map((point) => ({
      timestamp: parseMetricTimestamp(point.bucket_start),
      bucketStart: parseMetricTimestamp(point.bucket_start),
      bucketEnd: parseMetricTimestamp(point.bucket_end),
      value: roundMetric(point.avg),
      min: roundMetric(point.min),
      max: roundMetric(point.max),
      count: point.count,
    }));
}

function parseMetricTimestamp(value: string) {
  const timestamp = parseAbsoluteTimestamp(value);
  if (timestamp == null) {
    throw new Error(
      `Metric timestamp must include an explicit timezone: ${value}`,
    );
  }
  return timestamp;
}

function roundMetric(value: number) {
  return Number(value.toFixed(2));
}
