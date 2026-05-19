import {
  Card,
  CardBody,
  DataTable,
  IconTile,
  PageHeader,
  ProgressBar,
  SectionHeader,
  StatCard,
  StatusBadge,
  formatLocalDateTime,
} from "@golem/ui";
import {
  RiAlertLine,
  RiCpuLine,
  RiDatabase2Line,
  RiHardDrive3Line,
  RiMoneyDollarCircleLine,
  RiStackLine,
} from "@remixicon/react";
import { EndpointErrors, LoadingGrid } from "../../components/StateViews";
import type { NavigateTarget } from "../../components/types";
import { countVms, resourcePair, streamsTotals, utilization, vmStatusTone } from "../../lib/derived";
import { EMPTY_VALUE, formatCurrency, formatGlm, titleCase, vmStatusLabel } from "../../lib/format";
import { projectStreams, useStreamNowSeconds } from "../../lib/liveStreamValues";
import { glmToUsd, usdToGlm, useGlmUsdPrice } from "../../lib/prices";
import type { DashboardData } from "../../lib/useProviderData";

export function OverviewPage({
  data,
  loading,
  onNavigate,
}: {
  data: DashboardData | null;
  loading: boolean;
  onNavigate: (target: NavigateTarget) => void;
}) {
  const glmUsd = useGlmUsdPrice();
  const nowSeconds = useStreamNowSeconds();
  if (loading && !data) return <LoadingGrid />;
  const vms = data?.vms ?? [];
  const streams = projectStreams(data?.streams ?? [], nowSeconds);
  const counts = countVms(vms, streams);
  const totals = streamsTotals(streams);
  const totalEarnedUsd = glmToUsd(totals.vested, glmUsd);
  const { total, available } = resourcePair(data?.summary ?? undefined);
  const usedCpu = (total.cpu ?? 0) - (available.cpu ?? 0);
  const usedMemory = (total.memory ?? 0) - (available.memory ?? 0);
  const usedStorage = (total.storage ?? 0) - (available.storage ?? 0);
  const pricing = data?.summary?.pricing ?? {};
  const alerts = data?.alerts ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Provider Overview"
        description="Track your provider business, resources, and rented-out virtual machines."
      />
      <EndpointErrors errors={data?.errors ?? {}} />

      <div className="grid gap-4 md:grid-cols-3">
        <StatCard
          label="Total earned (USD)"
          value={formatCurrency(totalEarnedUsd)}
          detail={glmUsd == null ? "Waiting for GLM/USD quote" : "Converted from stream GLM"}
          icon={<RiMoneyDollarCircleLine className="h-5 w-5" />}
          tone="success"
        />
        <StatCard
          label="Total earned (GLM)"
          value={formatGlm(totals.vested, 4)}
          detail="Earned by elapsed stream time"
          icon={<RiStackLine className="h-5 w-5" />}
          tone="primary"
        />
        <StatCard
          label="Active VMs"
          value={counts.running}
          detail={`${counts.creating} creating`}
          icon={<RiStackLine className="h-5 w-5" />}
          tone="primary"
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.5fr_0.85fr]">
        <Card>
          <CardBody className="space-y-5">
            <SectionHeader title="Resources" />
            <div className="divide-y divide-border rounded-lg border border-border">
              <ResourceUsageRow
                icon={<RiCpuLine />}
                label="CPU"
                value={formatResourceUsage(usedCpu, total.cpu, "Cores")}
                progress={utilization(usedCpu, total.cpu)}
              />
              <ResourceUsageRow
                icon={<RiDatabase2Line />}
                label="Memory"
                value={formatResourceUsage(usedMemory, total.memory, "GB Memory")}
                progress={utilization(usedMemory, total.memory)}
              />
              <ResourceUsageRow
                icon={<RiHardDrive3Line />}
                label="Disk"
                value={formatResourceUsage(usedStorage, total.storage, "GB Disk")}
                progress={utilization(usedStorage, total.storage)}
              />
            </div>
            <button
              type="button"
              className="text-sm font-medium text-primary"
              onClick={() => onNavigate({ page: "monitoring" })}
            >
              View all resources
            </button>
          </CardBody>
        </Card>

        <Card>
          <CardBody className="space-y-4">
            <SectionHeader title="Pricing" description="Per month" />
            {[
              ["CPU", pricing.usd_per_core_month, pricing.glm_per_core_month],
              ["Memory", pricing.usd_per_gb_ram_month, pricing.glm_per_gb_ram_month],
              ["Storage", pricing.usd_per_gb_storage_month, pricing.glm_per_gb_storage_month],
            ].map(([label, usd, glm]) => {
              const usdValue = positiveNumber(usd);
              const glmValue = positiveNumber(glm) ?? usdToGlm(usdValue, glmUsd);
              return (
                <div
                  key={String(label)}
                  className="flex items-center justify-between gap-4 rounded-lg border border-border px-4 py-3"
                >
                  <span className="font-medium text-text-primary">{label}</span>
                  <span className="text-sm text-text-secondary">
                    {formatCurrency(usdValue)} / {formatGlm(glmValue)}
                  </span>
                </div>
              );
            })}
          </CardBody>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.1fr_0.8fr]">
        <Card>
          <CardBody>
            <SectionHeader
              title="Recent rented VMs"
              actions={
                <button
                  type="button"
                  className="text-sm font-medium text-primary"
                  onClick={() => onNavigate({ page: "vms" })}
                >
                  View all
                </button>
              }
            />
            <div className="mt-4">
              <DataTable
                rows={vms.slice(0, 4)}
                getRowKey={(vm) => vm.id}
                onRowClick={(vm) => onNavigate({ page: "vm-detail", vmId: vm.id })}
                empty="No rented VMs"
                columns={[
                  { key: "name", header: "Name", render: (vm) => vm.name },
                  {
                    key: "status",
                    header: "Status",
                    render: (vm) => (
                      <StatusBadge
                        label={vmStatusLabel(vm.status)}
                        tone={vmStatusTone(vm.status)}
                        busy={vm.transitioning}
                      />
                    ),
                  },
                  {
                    key: "uptime",
                    header: "Updated",
                    render: (vm) => formatLocalDateTime(vm.updated_at) ?? EMPTY_VALUE,
                  },
                ]}
              />
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardBody className="space-y-4">
            <SectionHeader
              title="Recent alerts"
              actions={
                <button
                  type="button"
                  className="text-sm font-medium text-primary"
                  onClick={() => onNavigate({ page: "alerts" })}
                >
                  View all
                </button>
              }
            />
            {alerts.length === 0 ? (
              <div className="text-sm text-text-secondary">No active alerts</div>
            ) : (
              alerts.slice(0, 3).map((alert) => (
                <div
                  key={`${alert.name}-${alert.vm_id ?? "host"}`}
                  className="rounded-lg border border-border px-4 py-3"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="font-medium text-text-primary">{alert.name}</div>
                    <StatusBadge label={titleCase(alert.severity)} tone={alert.severity === "critical" ? "danger" : "warning"} />
                  </div>
                  <div className="mt-1 text-sm text-text-secondary">
                    {alert.vm_id ?? alert.scope}
                  </div>
                </div>
              ))
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  );
}

function positiveNumber(value: unknown) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function formatResourceUsage(used: number, total?: number, unit?: string) {
  if (typeof total !== "number") return `${EMPTY_VALUE} ${unit}`;
  return `${Math.max(0, used)}/${total} ${unit}`;
}

function ResourceUsageRow({
  icon,
  label,
  value,
  progress,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  progress: number;
}) {
  return (
    <div className="grid gap-4 px-4 py-4 sm:grid-cols-[minmax(8rem,1fr)_minmax(10rem,18rem)_8rem] sm:items-center">
      <div className="flex items-center gap-3">
        <IconTile className="h-8 w-8" tone="neutral">
          <span className="[&>svg]:h-4 [&>svg]:w-4">{icon}</span>
        </IconTile>
        <span className="font-medium text-text-primary">{label}</span>
      </div>
      <ProgressBar value={progress} className="sm:justify-self-stretch" />
      <span className="text-sm font-medium text-text-secondary sm:text-right">
        {value}
      </span>
    </div>
  );
}
