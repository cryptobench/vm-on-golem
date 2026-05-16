import { formatLocalTime } from "@golem/ui";
import type {
  ActiveAlert,
  AlertRule,
  MetricsHistoryResponse,
  ProviderSummary,
  StreamStatus,
  VMInfo,
  VMResources,
  VMStatus,
} from "./types";
import { weiToToken } from "./format";

export type StatusTone = "success" | "warning" | "danger" | "neutral" | "primary";
export type ChartPoint = { label: string; value: number; secondaryValue?: number };

export function vmStatusTone(status: VMStatus): StatusTone {
  if (status === "running") return "success";
  if (status === "error") return "danger";
  if (status === "stopped" || status === "suspended" || status === "deleted") {
    return "neutral";
  }
  return "primary";
}

export function alertTone(severity: string): StatusTone {
  if (severity === "critical" || severity === "error") return "danger";
  if (severity === "warning") return "warning";
  return "neutral";
}

export function isVmActive(vm: VMInfo) {
  return !["deleted", "stopped", "error"].includes(vm.status);
}

export function countVms(vms: VMInfo[]) {
  return {
    all: vms.length,
    running: vms.filter((vm) => vm.status === "running").length,
    creating: vms.filter((vm) => vm.transitioning || vm.status === "creating").length,
    stopped: vms.filter((vm) => vm.status === "stopped").length,
    error: vms.filter((vm) => vm.status === "error").length,
  };
}

export function resourcePair(summary?: ProviderSummary) {
  const resources = summary?.resources ?? {};
  const total = (resources.total_resources ?? resources.total ?? {}) as Partial<VMResources>;
  const available = (resources.available_resources ?? resources.available ?? {}) as Partial<VMResources>;
  return { total, available };
}

export function utilization(used: number | undefined, total: number | undefined) {
  if (used == null || total == null || total <= 0) return 0;
  return Math.round((used / total) * 100);
}

export function metricNumber(source: Record<string, unknown> | undefined, key: string) {
  const value = source?.[key];
  return typeof value === "number" ? value : null;
}

export function streamsTotals(streams: StreamStatus[]) {
  return streams.reduce(
    (totals, stream) => {
      totals.vested += weiToToken(stream.computed.vested_wei) ?? 0;
      totals.withdrawable += weiToToken(stream.computed.withdrawable_wei) ?? 0;
      totals.deposit += weiToToken(stream.chain.deposit) ?? 0;
      return totals;
    },
    { vested: 0, withdrawable: 0, deposit: 0 },
  );
}

export function chartPoints(
  history: MetricsHistoryResponse | null | undefined,
  metric: string,
): ChartPoint[] {
  const points = history?.points ?? [];
  return points
    .filter((point) => point.metric === metric)
    .map((point) => ({
      label: sampleLabel(point.bucket_start),
      value: Number(point.avg.toFixed(2)),
    }));
}

function sampleLabel(timestamp: string) {
  return formatLocalTime(timestamp) ?? timestamp;
}

export function streamEarningsPoints(streams: StreamStatus[]): ChartPoint[] {
  return streams.map((stream) => ({
    label: stream.vm_id,
    value: Number((weiToToken(stream.computed.vested_wei) ?? 0).toFixed(4)),
  }));
}

export function enabledRules(rules: AlertRule[]) {
  return rules.filter((rule) => rule.enabled).length;
}

export function severityCount(alerts: ActiveAlert[], severity: string) {
  return alerts.filter((alert) => alert.severity === severity).length;
}
