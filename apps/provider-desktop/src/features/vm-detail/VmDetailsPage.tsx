import React from "react";
import {
  Button,
  Card,
  CardBody,
  ConfirmDialog,
  KeyValueList,
  ProgressBar,
  SectionHeader,
  StatCard,
  StatusBadge,
  Tabs,
  TimeSeriesAreaChart,
} from "@golem/ui";
import {
  RiArrowLeftLine,
  RiCheckboxCircleLine,
  RiCloseCircleLine,
  RiCpuLine,
  RiFileCopyLine,
  RiHardDrive3Line,
} from "@remixicon/react";
import { EmptyPanel, EndpointErrors, LoadingGrid } from "../../components/StateViews";
import { metricChartPoints } from "../../components/metricChartPoints";
import { RangePicker } from "../../components/RangePicker";
import type { NavigateTarget } from "../../components/types";
import { metricNumber, vmStatusTone } from "../../lib/derived";
import {
  EMPTY_VALUE,
  formatBytes,
  formatDateTime,
  formatDuration,
  formatGlm,
  shortAddress,
  titleCase,
  vmStatusLabel,
  weiToToken,
} from "../../lib/format";
import { projectStream, useStreamNowSeconds } from "../../lib/liveStreamValues";
import { providerApi } from "../../lib/providerApi";
import type { HistoryRange, MetricsHistoryResponse, VMInfo } from "../../lib/types";
import { useVmDetail, useVmMetricHistory } from "../../lib/useProviderData";

type VmTab = "overview" | "metrics" | "stream" | "settings";

export function VmDetailsPage({
  vmId,
  onNavigate,
}: {
  vmId: string;
  onNavigate: (target: NavigateTarget) => void;
}) {
  const [tab, setTab] = React.useState<VmTab>("overview");
  const { data, loading, refresh } = useVmDetail(vmId);
  const vm = data?.vm;
  const latestVmMetrics = data?.latest?.vms?.[vmId] ?? {};

  if (loading && !data) return <LoadingGrid />;

  return (
    <div className="space-y-6">
      <div className="flex min-w-0 items-start gap-3 border-b border-border pb-6">
        <button
          type="button"
          className="mt-1 grid h-8 w-8 place-items-center rounded-full text-text-secondary hover:bg-surface-muted hover:text-text-primary"
          onClick={() => onNavigate({ page: "vms" })}
          aria-label="Back to virtual machines"
        >
          <RiArrowLeftLine className="h-5 w-5" aria-hidden />
        </button>
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-semibold tracking-tight text-text-primary">
              VM Details - {vm?.name ?? vmId}
            </h1>
            <StatusBadge
              label={vm ? vmStatusLabel(vm.status) : "Unknown"}
              tone={vm ? vmStatusTone(vm.status) : "neutral"}
              busy={vm?.transitioning}
            />
          </div>
          <p className="mt-1 text-sm text-text-secondary">
            {vm?.status_message ?? "Loading VM details"}
          </p>
        </div>
      </div>

      <EndpointErrors errors={data?.errors ?? {}} />

      <Tabs<VmTab>
        tabs={[
          { id: "overview", label: "Overview" },
          { id: "metrics", label: "Metrics" },
          { id: "stream", label: "Stream" },
          { id: "settings", label: "Settings" },
        ]}
        active={tab}
        onChange={setTab}
      />

      {tab === "overview" ? (
        <OverviewTab
          vmId={vmId}
          data={data}
          latestVmMetrics={latestVmMetrics}
          onRefresh={refresh}
        />
      ) : null}
      {tab === "metrics" ? (
        <MetricsTab
          vmId={vmId}
          latestVmMetrics={latestVmMetrics}
        />
      ) : null}
      {tab === "stream" ? <StreamTab data={data} /> : null}
      {tab === "settings" ? (
        <SettingsTab vmId={vmId} vm={vm ?? null} onRefresh={refresh} />
      ) : null}
    </div>
  );
}

function OverviewTab({
  vmId,
  data,
  latestVmMetrics,
  onRefresh,
}: {
  vmId: string;
  data: ReturnType<typeof useVmDetail>["data"];
  latestVmMetrics: Record<string, unknown>;
  onRefresh: () => void;
}) {
  const vm = data?.vm;
  const access = data?.access;
  const nowSeconds = useStreamNowSeconds();
  const stream = data?.stream ? projectStream(data.stream, nowSeconds) : null;
  return (
    <div className="space-y-6">
      <div className="grid gap-4">
        <Card>
          <CardBody>
            <SectionHeader title="VM Overview" />
            <KeyValueList
              className="mt-4"
              items={[
                { key: "status", label: "Status", value: vm ? <StatusBadge label={vmStatusLabel(vm.status)} tone={vmStatusTone(vm.status)} busy={vm.transitioning} /> : EMPTY_VALUE },
                { key: "stage", label: "Lifecycle stage", value: titleCase(vm?.lifecycle_stage) },
                { key: "resources", label: "Resources", value: vm ? `${vm.resources.cpu} vCPU - ${vm.resources.memory} GB - ${vm.resources.storage} GB` : EMPTY_VALUE },
                { key: "ip", label: "IP Address", value: vm?.ip_address ?? EMPTY_VALUE },
                { key: "ssh", label: "SSH Port", value: vm?.ssh_port ?? EMPTY_VALUE },
                { key: "created", label: "Created At", value: formatDateTime(vm?.created_at) },
                { key: "updated", label: "Updated At", value: formatDateTime(vm?.updated_at) },
              ]}
            />
          </CardBody>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardBody>
            <SectionHeader title="Stream Status" />
            <KeyValueList
              className="mt-4"
              items={[
                { key: "stream_id", label: "Stream ID", value: stream?.stream_id ?? EMPTY_VALUE },
                { key: "verified", label: "Verified", value: stream?.verified ? "Yes" : stream ? "No" : EMPTY_VALUE },
                { key: "rate", label: "Rate per second", value: formatGlm(weiToToken(stream?.chain.ratePerSecond), 6) },
                { key: "remaining", label: "Remaining", value: formatDuration(stream?.computed.remaining_seconds) },
              ]}
            />
          </CardBody>
        </Card>
        <Card>
          <CardBody>
            <SectionHeader title="Access" />
            <KeyValueList
              className="mt-4"
              items={[
                { key: "host", label: "SSH Host", value: access?.ssh_host ?? EMPTY_VALUE },
                { key: "port", label: "SSH Port", value: access?.ssh_port ?? EMPTY_VALUE },
                { key: "user", label: "SSH User", value: access?.ssh_user ?? EMPTY_VALUE },
              ]}
            />
            {access?.ssh_host && access.ssh_port && access.ssh_user ? (
              <button
                type="button"
                className="mt-4 inline-flex items-center gap-2 text-sm font-medium text-primary"
                onClick={() => void navigator.clipboard.writeText(`ssh ${access.ssh_user}@${access.ssh_host} -p ${access.ssh_port}`)}
              >
                <RiFileCopyLine className="h-4 w-4" aria-hidden />
                Copy SSH Command
              </button>
            ) : null}
          </CardBody>
        </Card>
      </div>

      <ProviderActions vmId={vmId} vm={vm ?? null} onRefresh={onRefresh} />

      <div className="grid gap-4 md:grid-cols-4">
        <StatCard label="CPU" value={`${metricNumber(latestVmMetrics, "cpu_percent") ?? EMPTY_VALUE}%`} icon={<RiCpuLine className="h-5 w-5" />} />
        <StatCard label="Memory" value={formatBytes(latestVmMetrics.memory_used_bytes)} icon={<RiCpuLine className="h-5 w-5" />} />
        <StatCard label="Disk" value={formatBytes(latestVmMetrics.disk_used_bytes)} icon={<RiHardDrive3Line className="h-5 w-5" />} />
        <StatCard label="Network RX" value={formatBytes(latestVmMetrics.network_rx_bytes)} icon={<RiHardDrive3Line className="h-5 w-5" />} />
      </div>
    </div>
  );
}

function MetricsTab({
  vmId,
  latestVmMetrics,
}: {
  vmId: string;
  latestVmMetrics: Record<string, unknown>;
}) {
  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-4">
        <StatCard label="CPU" value={`${metricNumber(latestVmMetrics, "cpu_percent") ?? EMPTY_VALUE}%`} detail="Current usage" icon={<RiCpuLine className="h-5 w-5" />} tone="primary" />
        <StatCard label="Memory" value={`${formatBytes(latestVmMetrics.memory_used_bytes)} / ${formatBytes(latestVmMetrics.memory_total_bytes)}`} detail="Current usage" icon={<RiCpuLine className="h-5 w-5" />} tone="primary" />
        <StatCard label="Disk" value={`${formatBytes(latestVmMetrics.disk_used_bytes)} / ${formatBytes(latestVmMetrics.disk_total_bytes)}`} detail="Current usage" icon={<RiHardDrive3Line className="h-5 w-5" />} tone="success" />
        <StatCard label="Network" value={formatBytes(latestVmMetrics.network_rx_bytes)} detail={`${formatBytes(latestVmMetrics.network_tx_bytes)} TX`} icon={<RiHardDrive3Line className="h-5 w-5" />} tone="primary" />
      </div>
      <VmMetricCharts vmId={vmId} />
    </div>
  );
}

function VmMetricCharts({ vmId }: { vmId: string }) {
  const [range, setRange] = React.useState<HistoryRange>("1h");
  const history = useVmMetricHistory(vmId, range);

  return (
    <div className="space-y-4">
      {history.error ? <EndpointErrors errors={{ history: history.error }} /> : null}
      <MetricChart title="CPU (%)" metric="cpu_percent" history={history.history} range={range} setRange={setRange} />
      <MetricChart title="Memory" metric="memory_used_bytes" history={history.history} range={range} setRange={setRange} />
    </div>
  );
}

function MetricChart({
  title,
  metric,
  history,
  range,
  setRange,
}: {
  title: string;
  metric: string;
  history: MetricsHistoryResponse | null;
  range: HistoryRange;
  setRange: (range: HistoryRange) => void;
}) {
  return (
    <Card>
      <CardBody>
        <div className="mb-4 flex items-center justify-between gap-3">
          <h2 className="text-base font-semibold text-text-primary">{title}</h2>
          <RangePicker value={range} onChange={setRange} />
        </div>
        <TimeSeriesAreaChart
          data={metricChartPoints(history, metric)}
          range={range}
          height={240}
          yUnit={metric === "cpu_percent" ? "%" : undefined}
          valueFormatter={metric.endsWith("_bytes") ? formatBytes : undefined}
        />
      </CardBody>
    </Card>
  );
}

function StreamTab({ data }: { data: ReturnType<typeof useVmDetail>["data"] }) {
  const nowSeconds = useStreamNowSeconds();
  const stream = data?.stream ? projectStream(data.stream, nowSeconds) : null;
  if (!stream) return <EmptyPanel title="No stream data" detail={data?.errors.stream} />;
  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_0.7fr]">
      <Card>
        <CardBody>
          <SectionHeader title="Stream Overview" />
          <KeyValueList
            className="mt-4"
            items={[
              { key: "vm", label: "VM ID", value: stream.vm_id },
              { key: "stream", label: "Stream ID", value: stream.stream_id },
              { key: "verified", label: "Verified", value: stream.verified ? "true" : "false", icon: stream.verified ? <RiCheckboxCircleLine className="h-4 w-4 text-success" /> : undefined },
              { key: "reason", label: "Reason", value: stream.reason },
              { key: "token", label: "Token address", value: shortAddress(stream.chain.token) },
              { key: "sender", label: "Sender", value: shortAddress(stream.chain.sender) },
              { key: "recipient", label: "Recipient", value: shortAddress(stream.chain.recipient) },
              { key: "state", label: "Payment state", value: stream.payment_state ?? "unknown" },
            ]}
          />
        </CardBody>
      </Card>
      <Card>
        <CardBody>
          <SectionHeader title="Computed Values" />
          <KeyValueList
            className="mt-4"
            items={[
              { key: "remaining", label: "Remaining", value: formatDuration(stream.computed.remaining_seconds) },
              { key: "vested", label: "Total earned", value: formatGlm(weiToToken(stream.computed.vested_wei), 4) },
              { key: "withdrawable", label: "Withdrawable", value: formatGlm(weiToToken(stream.computed.withdrawable_wei), 4) },
              { key: "deposit", label: "Deposit", value: formatGlm(weiToToken(stream.chain.deposit)) },
              { key: "withdrawn", label: "Withdrawn", value: formatGlm(weiToToken(stream.chain.withdrawn)) },
            ]}
          />
        </CardBody>
      </Card>
    </div>
  );
}

function SettingsTab({
  vmId,
  vm,
  onRefresh,
}: {
  vmId: string;
  vm: VMInfo | null;
  onRefresh: () => void;
}) {
  return <ProviderActions vmId={vmId} vm={vm} onRefresh={onRefresh} />;
}

function ProviderActions({
  vmId,
  vm,
  onRefresh,
}: {
  vmId: string;
  vm: VMInfo | null;
  onRefresh: () => void;
}) {
  const [busy, setBusy] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = React.useState(false);
  const run = async (key: string, action: () => Promise<unknown>) => {
    setBusy(key);
    setError(null);
    try {
      await action();
      onRefresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  };
  const terminated = vm?.status === "terminated";
  const disabled = !vm || terminated || vm.transitioning || busy !== null;
  return (
    <Card>
      <CardBody>
        <SectionHeader title="Provider Actions" />
        {error ? <div className="mt-3 text-sm text-danger">{error}</div> : null}
        {vm?.transitioning ? <ProgressBar className="mt-4" value={vm.progress} /> : null}
        <div className="mt-4 grid gap-3 md:grid-cols-[minmax(0,18rem)]">
          <Button
            variant="danger"
            busy={busy === "terminate"}
            disabled={disabled}
            onClick={() => setConfirmOpen(true)}
          >
            <RiCloseCircleLine className="h-4 w-4" aria-hidden />
            Terminate Lease
          </Button>
        </div>
      </CardBody>
      <ConfirmDialog
        open={confirmOpen}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={() =>
          run("terminate", async () => {
            await providerApi.terminateLease(vmId);
            setConfirmOpen(false);
          })
        }
        title="Terminate Lease"
        description="This submits an on-chain termination from the provider wallet, so the provider pays gas. The VM is deleted only after the lease is confirmed terminated."
        confirmLabel="Terminate Lease"
        danger
        busy={busy === "terminate"}
      />
    </Card>
  );
}
