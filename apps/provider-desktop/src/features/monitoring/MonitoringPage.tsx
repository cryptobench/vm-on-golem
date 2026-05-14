import React from "react";
import {
  Card,
  CardBody,
  DataTable,
  LineAreaChart,
  PageHeader,
  ProgressBar,
  StatCard,
} from "@golem/ui";
import { RiCpuLine, RiDownloadLine, RiHardDrive3Line, RiLineChartLine, RiUploadLine } from "@remixicon/react";
import { EndpointErrors, LoadingGrid } from "../../components/StateViews";
import { metricChartPoints } from "../../components/metricChartPoints";
import { RangePicker } from "../../components/RangePicker";
import { EMPTY_VALUE, formatBytes, formatPercent } from "../../lib/format";
import type { HistoryRange } from "../../lib/types";
import type { DashboardData } from "../../lib/useProviderData";
import { useHostMonitoringLive } from "./useHostMonitoringLive";

export function MonitoringPage({
  data,
  loading,
}: {
  data: DashboardData | null;
  loading: boolean;
}) {
  const [range, setRange] = React.useState<HistoryRange>("1h");
  const live = useHostMonitoringLive(range);

  if (loading && !data && !live.state.metricsLatest) return <LoadingGrid />;
  const host = live.state.metricsLatest?.host ?? {};
  const cpu = metricNumber(host, "cpu_percent");
  const memoryUsed = metricNumber(host, "memory_used_bytes");
  const memoryTotal = metricNumber(host, "memory_total_bytes");
  const diskUsed = metricNumber(host, "disk_used_bytes");
  const diskTotal = metricNumber(host, "disk_total_bytes");
  const networkRx = metricNumber(host, "network_rx_bytes");
  const networkTx = metricNumber(host, "network_tx_bytes");
  const effectiveHistory = live.state.metricsHistory;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Monitoring"
        description="Track host performance and VM usage."
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

      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardBody>
            <div className="mb-4 flex items-center justify-between gap-3">
              <h2 className="text-base font-semibold text-text-primary">Host CPU Usage</h2>
              <RangePicker value={range} onChange={setRange} />
            </div>
            <LineAreaChart data={metricChartPoints(effectiveHistory, "cpu_percent")} yUnit="%" height={240} />
          </CardBody>
        </Card>
        <Card>
          <CardBody>
            <div className="mb-4 flex items-center justify-between gap-3">
              <h2 className="text-base font-semibold text-text-primary">Host Memory Usage</h2>
              <RangePicker value={range} onChange={setRange} />
            </div>
            <LineAreaChart
              data={metricChartPoints(effectiveHistory, "memory_used_bytes")}
              height={240}
              valueFormatter={formatBytes}
            />
          </CardBody>
        </Card>
      </div>

      <Card>
        <CardBody className="p-0">
          <div className="p-4">
            <h2 className="text-base font-semibold text-text-primary">VM Metrics</h2>
          </div>
          <DataTable
            rows={data?.monitoring?.vms ?? []}
            getRowKey={(row, index) => String(row.vm_id ?? index)}
            empty="No VM metrics have been sampled"
            columns={[
              { key: "name", header: "Name", render: (row) => String(row.vm_id ?? EMPTY_VALUE) },
              {
                key: "cpu",
                header: "CPU %",
                render: (row) => (
                  <div className="flex min-w-32 items-center gap-3">
                    <span>{formatPercent(typeof row.cpu_percent === "number" ? row.cpu_percent : null)}</span>
                    <ProgressBar value={typeof row.cpu_percent === "number" ? row.cpu_percent : 0} className="w-16" />
                  </div>
                ),
              },
              {
                key: "memory",
                header: "Memory (Used / Total)",
                render: (row) => `${formatBytes(row.memory_used_bytes)} / ${formatBytes(row.memory_total_bytes)}`,
              },
              {
                key: "disk",
                header: "Disk (Used / Total)",
                render: (row) => `${formatBytes(row.disk_used_bytes)} / ${formatBytes(row.disk_total_bytes)}`,
              },
              {
                key: "network",
                header: "Network (RX / TX)",
                render: (row) => `${formatBytes(row.network_rx_bytes)} / ${formatBytes(row.network_tx_bytes)}`,
              },
              { key: "agent", header: "Agent Version", render: (row) => String(row.agent_version ?? EMPTY_VALUE) },
            ]}
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
