import {
  Card,
  CardBody,
  DataTable,
  IconTile,
  LineAreaChart,
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
  RiLineChartLine,
  RiMoneyDollarCircleLine,
  RiStackLine,
} from "@remixicon/react";
import { EndpointErrors, LoadingGrid } from "../../components/StateViews";
import type { NavigateTarget } from "../../components/types";
import { countVms, resourcePair, streamEarningsPoints, streamsTotals, utilization, vmStatusTone } from "../../lib/derived";
import { EMPTY_VALUE, formatCurrency, formatGlm, formatPercent, titleCase, vmStatusLabel } from "../../lib/format";
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
  if (loading && !data) return <LoadingGrid />;
  const vms = data?.vms ?? [];
  const counts = countVms(vms);
  const totals = streamsTotals(data?.streams ?? []);
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

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Total earned (USD)"
          value={formatCurrency(totalEarnedUsd)}
          detail={glmUsd == null ? "Waiting for GLM/USD quote" : "Converted from active stream GLM"}
          icon={<RiMoneyDollarCircleLine className="h-5 w-5" />}
          tone="success"
        />
        <StatCard
          label="Total earned (GLM)"
          value={formatGlm(totals.vested)}
          detail="From active stream values"
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
        <StatCard
          label="Service health"
          value={titleCase(data?.monitoring?.status ?? data?.summary?.status)}
          detail={formatLocalDateTime(data?.monitoring?.last_sample_at) ?? "Last sample unavailable"}
          icon={<RiLineChartLine className="h-5 w-5" />}
          tone={data?.monitoring?.status === "healthy" ? "success" : "neutral"}
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.5fr_0.85fr]">
        <Card>
          <CardBody className="space-y-5">
            <SectionHeader title="Resources" />
            <div className="grid gap-6 md:grid-cols-3">
              <ResourceColumn
                title="Total resources"
                cpu={total.cpu}
                memory={total.memory}
                storage={total.storage}
              />
              <ResourceColumn
                title="Available resources"
                cpu={available.cpu}
                memory={available.memory}
                storage={available.storage}
              />
              <div className="space-y-4">
                <h3 className="text-sm font-medium text-text-secondary">Utilization</h3>
                <Utilization label="CPU" value={utilization(usedCpu, total.cpu)} />
                <Utilization
                  label="Memory"
                  value={utilization(usedMemory, total.memory)}
                />
                <Utilization
                  label="Storage"
                  value={utilization(usedStorage, total.storage)}
                />
              </div>
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

      <div className="grid gap-4 xl:grid-cols-[1.1fr_1fr_0.8fr]">
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
          <CardBody>
            <SectionHeader title="Earnings trend (GLM)" description={formatGlm(totals.vested)} />
            <LineAreaChart data={streamEarningsPoints(data?.streams ?? [])} height={220} />
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

function ResourceColumn({
  title,
  cpu,
  memory,
  storage,
}: {
  title: string;
  cpu?: number;
  memory?: number;
  storage?: number;
}) {
  return (
    <div className="space-y-3">
      <h3 className="text-sm font-medium text-text-secondary">{title}</h3>
      <ResourceRow icon={<RiCpuLine />} label={`${cpu ?? EMPTY_VALUE} CPU`} />
      <ResourceRow icon={<RiDatabase2Line />} label={`${memory ?? EMPTY_VALUE} GB RAM`} />
      <ResourceRow icon={<RiHardDrive3Line />} label={`${storage ?? EMPTY_VALUE} GB Storage`} />
    </div>
  );
}

function ResourceRow({ icon, label }: { icon: React.ReactNode; label: string }) {
  return (
    <div className="flex items-center gap-3 text-sm text-text-primary">
      <IconTile className="h-7 w-7" tone="neutral">
        <span className="[&>svg]:h-4 [&>svg]:w-4">{icon}</span>
      </IconTile>
      {label}
    </div>
  );
}

function Utilization({ label, value }: { label: string; value: number }) {
  return (
    <div className="grid grid-cols-[4rem_1fr_3rem] items-center gap-3 text-sm">
      <span className="font-medium text-text-primary">{label}</span>
      <ProgressBar value={value} />
      <span className="text-right text-text-secondary">{formatPercent(value, 0)}</span>
    </div>
  );
}
