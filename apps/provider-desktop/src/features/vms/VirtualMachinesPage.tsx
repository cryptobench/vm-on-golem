import React from "react";
import {
  ActionMenu,
  Card,
  CardBody,
  DataTable,
  PageHeader,
  ProgressBar,
  StatCard,
  StatusBadge,
  TextInput,
  ToggleSwitch,
} from "@golem/ui";
import {
  RiAlertLine,
  RiLoader4Line,
  RiSearchLine,
  RiStackLine,
  RiStopCircleLine,
} from "@remixicon/react";
import { EndpointErrors, LoadingGrid } from "../../components/StateViews";
import type { NavigateTarget } from "../../components/types";
import { countVms, vmStatusTone } from "../../lib/derived";
import { EMPTY_VALUE, vmStatusLabel } from "../../lib/format";
import type { DashboardData } from "../../lib/useProviderData";
import type { VMInfo } from "../../lib/types";

export function VirtualMachinesPage({
  data,
  loading,
  onNavigate,
}: {
  data: DashboardData | null;
  loading: boolean;
  onNavigate: (target: NavigateTarget) => void;
}) {
  const [search, setSearch] = React.useState("");
  const [showTerminated, setShowTerminated] = React.useState(false);
  if (loading && !data) return <LoadingGrid />;

  const vms = data?.vms ?? [];
  const counts = countVms(vms);
  const filtered = vms.filter((vm) => {
    const matches = vm.name.toLowerCase().includes(search.toLowerCase());
    const visible = showTerminated || !["deleted"].includes(vm.status);
    return matches && visible;
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Virtual Machines"
        description="Monitor the virtual machines currently rented out from your provider."
      />
      <EndpointErrors errors={data?.errors ?? {}} />

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <StatCard label="All" value={counts.all} detail="Total VMs" icon={<RiStackLine className="h-5 w-5" />} tone="neutral" />
        <StatCard label="Running" value={counts.running} detail="VMs" icon={<RiStackLine className="h-5 w-5" />} tone="success" />
        <StatCard label="Creating" value={counts.creating} detail="VMs" icon={<RiLoader4Line className="h-5 w-5" />} tone="primary" />
        <StatCard label="Stopped" value={counts.stopped} detail="VMs" icon={<RiStopCircleLine className="h-5 w-5" />} tone="neutral" />
        <StatCard label="Error" value={counts.error} detail="VMs" icon={<RiAlertLine className="h-5 w-5" />} tone="danger" />
      </div>

      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <label className="relative w-full max-w-md">
          <RiSearchLine className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" aria-hidden />
          <TextInput
            className="pl-10"
            placeholder="Search VMs..."
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>
        <div className="flex items-center gap-3 text-sm text-text-secondary">
          Show terminated VMs
          <ToggleSwitch
            checked={showTerminated}
            onChange={setShowTerminated}
            label="Show terminated VMs"
          />
        </div>
      </div>

      <Card>
        <CardBody className="p-0">
          <DataTable
            rows={filtered}
            getRowKey={(vm) => vm.id}
            onRowClick={(vm) => onNavigate({ page: "vm-detail", vmId: vm.id })}
            empty="No virtual machines match the current filters"
            columns={[
              {
                key: "name",
                header: "Name",
                render: (vm) => <span className="font-medium">{vm.name}</span>,
              },
              {
                key: "status",
                header: "Status",
                render: (vm) => <VmStatus vm={vm} />,
              },
              {
                key: "resources",
                header: "Resources",
                render: (vm) => (
                  <span>
                    {vm.resources.cpu} vCPU<br />
                    {vm.resources.memory} GB RAM<br />
                    {vm.resources.storage} GB Storage
                  </span>
                ),
              },
              { key: "ip", header: "IP Address", render: (vm) => vm.ip_address ?? EMPTY_VALUE },
              { key: "ssh", header: "SSH Port", render: (vm) => vm.ssh_port ?? EMPTY_VALUE },
              { key: "updated", header: "Updated", render: (vm) => new Date(vm.updated_at).toLocaleString() },
              {
                key: "actions",
                header: "",
                render: (vm) => (
                  <ActionMenu
                    items={[
                      { label: "Open details", onSelect: () => onNavigate({ page: "vm-detail", vmId: vm.id }) },
                    ]}
                  />
                ),
              },
            ]}
          />
          <div className="border-t border-border px-4 py-3 text-sm text-text-secondary">
            Showing {filtered.length} of {vms.length} VMs
          </div>
        </CardBody>
      </Card>
    </div>
  );
}

function VmStatus({ vm }: { vm: VMInfo }) {
  return (
    <div className="space-y-2">
      <StatusBadge
        label={vmStatusLabel(vm.status)}
        tone={vmStatusTone(vm.status)}
        busy={vm.transitioning}
      />
      {vm.transitioning ? (
        <div className="w-32">
          <ProgressBar value={vm.progress} />
        </div>
      ) : vm.error_message ? (
        <div className="text-xs text-danger">{vm.error_message}</div>
      ) : null}
    </div>
  );
}
