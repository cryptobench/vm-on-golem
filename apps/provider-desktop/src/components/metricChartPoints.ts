import { formatLocalTime } from "@golem/ui";
import type { MetricSample, MetricsHistoryResponse } from "../lib/types";

export type MetricChartPoint = {
  label: string;
  value: number;
  secondaryValue?: number;
};

export function metricChartPoints(
  history: MetricsHistoryResponse | null | undefined,
  metric: string,
): MetricChartPoint[] {
  const samples = history?.samples ?? [];
  return samples
    .filter((sample) => sample.metric === metric)
    .map((sample) => ({
      label: formatMetricSampleTime(sample),
      value: Number(sample.value.toFixed(2)),
    }));
}

function formatMetricSampleTime(sample: MetricSample) {
  const label = formatLocalTime(sample.timestamp);
  if (!label) {
    throw new Error(
      `Metric timestamp must include an explicit timezone: ${sample.timestamp}`,
    );
  }
  return label;
}
