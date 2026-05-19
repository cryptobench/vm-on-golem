import React from "react";
import {
  Card,
  CardBody,
  PageHeader,
  StatCard,
  TimeSeriesAreaChart,
} from "@golem/ui";
import { RiCpuLine, RiDownloadLine, RiHardDrive3Line, RiLineChartLine, RiUploadLine } from "@remixicon/react";
import { EndpointErrors, LoadingGrid } from "../../components/StateViews";
import { metricChartPoints } from "../../components/metricChartPoints";
import { RangePicker } from "../../components/RangePicker";
import { EMPTY_VALUE, formatBytes, formatPercent } from "../../lib/format";
import type { HistoryRange, MetricsHistoryResponse } from "../../lib/types";
import type { DashboardData } from "../../lib/useProviderData";
import { useHostMonitoringLive } from "./useHostMonitoringLive";

export function MonitoringPage({
  data,
  loading,
}: {
  data: DashboardData | null;
  loading: boolean;
}) {
  const live = useHostMonitoringLive();

  if (loading && !data && !live.state.metricsLatest) return <LoadingGrid />;
  const host = live.state.metricsLatest?.host ?? {};
  const cpu = metricNumber(host, "cpu_percent");
  const memoryUsed = metricNumber(host, "memory_used_bytes");
  const memoryTotal = metricNumber(host, "memory_total_bytes");
  const diskUsed = metricNumber(host, "disk_used_bytes");
  const diskTotal = metricNumber(host, "disk_total_bytes");
  const networkRx = metricNumber(host, "network_rx_bytes");
  const networkTx = metricNumber(host, "network_tx_bytes");

  return (
    <div className="space-y-6">
      <PageHeader
        title="Monitoring"
        description="Track host performance."
      />
      <EndpointErrors
        errors={{
          ...(data?.errors ?? {}),
          ...(live.error ? { hostLive: live.error } : {}),
        }}
      />

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Host CPU" value={formatPercent(cpu)} detail="% of total" icon={<RiCpuLine className="h-5 w-5" />} tone="primary" />
        <StatCard label="Host Memory" value={`${formatBytes(memoryUsed)} / ${formatBytes(memoryTotal)}`} detail={memoryUsed != null && memoryTotal ? formatPercent((memoryUsed / memoryTotal) * 100) : EMPTY_VALUE} icon={<RiLineChartLine className="h-5 w-5" />} tone="primary" />
        <StatCard label="Host Disk" value={`${formatBytes(diskUsed)} / ${formatBytes(diskTotal)}`} detail={diskUsed != null && diskTotal ? formatPercent((diskUsed / diskTotal) * 100) : EMPTY_VALUE} icon={<RiHardDrive3Line className="h-5 w-5" />} tone="primary" />
        <StatCard label="Host Load" value={metricNumber(host, "load_1m") ?? EMPTY_VALUE} detail="1m average" icon={<RiLineChartLine className="h-5 w-5" />} tone="primary" />
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <StatCard label="Network RX" value={formatBytes(networkRx)} detail="Total received" icon={<RiDownloadLine className="h-5 w-5" />} tone="success" />
        <StatCard label="Network TX" value={formatBytes(networkTx)} detail="Total transmitted" icon={<RiUploadLine className="h-5 w-5" />} tone="success" />
      </div>

      <HostUsageCharts
        history={live.state.metricsHistory}
        onRangeChange={live.setHistoryRange}
      />
    </div>
  );
}

function HostUsageCharts({
  history,
  onRangeChange,
}: {
  history: MetricsHistoryResponse | null;
  onRangeChange: (range: HistoryRange) => void;
}) {
  const [range, setRange] = React.useState<HistoryRange>("1h");

  const handleRangeChange = React.useCallback(
    (nextRange: HistoryRange) => {
      if (nextRange === range) return;
      setRange(nextRange);
      onRangeChange(nextRange);
    },
    [onRangeChange, range],
  );

  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <Card>
        <CardBody>
          <div className="mb-4 flex items-center justify-between gap-3">
            <h2 className="text-base font-semibold text-text-primary">Host CPU Usage</h2>
            <RangePicker value={range} onChange={handleRangeChange} />
          </div>
          <TimeSeriesAreaChart
            data={metricChartPoints(history, "cpu_percent")}
            range={range}
            yUnit="%"
            height={240}
          />
        </CardBody>
      </Card>
      <Card>
        <CardBody>
          <div className="mb-4 flex items-center justify-between gap-3">
            <h2 className="text-base font-semibold text-text-primary">Host Memory Usage</h2>
            <RangePicker value={range} onChange={handleRangeChange} />
          </div>
          <TimeSeriesAreaChart
            data={metricChartPoints(history, "memory_used_bytes")}
            range={range}
            height={240}
            valueFormatter={formatBytes}
          />
        </CardBody>
      </Card>
    </div>
  );
}

function metricNumber(source: Record<string, unknown> | undefined, key: string) {
  const value = source?.[key];
  if (typeof value === "number") return value;
  if (value && typeof value === "object") {
    const nested = (value as { value?: unknown }).value;
    return typeof nested === "number" ? nested : null;
  }
  return null;
}
