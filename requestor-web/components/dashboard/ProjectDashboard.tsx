"use client";

import React from "react";
import { useProjects } from "../../context/ProjectsContext";
import { useProjectVmModels } from "../../hooks/useProjectVmModels";
import { DashboardSkeleton } from "./DashboardSkeleton";
import { DashboardEmptyState } from "./DashboardEmptyState";
import { DashboardSection } from "./DashboardSection";
import { DashboardSummaryCard } from "./DashboardSummaryCard";
import { ActiveStreamsTable, ActiveVmsTable } from "./DashboardTables";
import { useDashboardStreams } from "./useDashboardStreams";
import { isTerminalVmStatus } from "../../lib/requestorVmModel";

function formatToken(value: number, token: string, digits = 2) {
  return `${value.toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: value > 0 ? Math.min(2, digits) : 0 })} ${token}`;
}

export function ProjectDashboard() {
  const { activeId } = useProjects();
  const { items, isInitialLoading: rentalsLoading } =
    useProjectVmModels(activeId);
  const [mounted, setMounted] = React.useState(false);
  React.useEffect(() => setMounted(true), []);

  const activeVms = items.filter(
    (vm) => !isTerminalVmStatus(vm.lifecycle.status),
  );
  const activeStreamRentals = activeVms
    .filter((vm) => vm.rental.stream_id)
    .map((vm) => vm.rental);
  const runningCount = activeVms.filter(
    (vm) => vm.lifecycle.status === "running",
  ).length;
  const {
    rows: streamRows,
    totalSpent,
    isInitialLoading: streamsLoading,
  } = useDashboardStreams(activeStreamRentals);
  const activeStreamRows = streamRows.filter((row) => row.status === "Active");

  if (!mounted || rentalsLoading || streamsLoading)
    return <DashboardSkeleton />;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-text-primary">
          Dashboard
        </h1>
        <p className="mt-1 text-sm text-text-secondary">
          Overview of your resources and usage.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <DashboardSummaryCard
          title="Active VMs"
          value={String(activeVms.length)}
          visual="vms"
          meta={
            activeVms.length ? (
              <span>
                <span className="mr-2 inline-block h-2 w-2 rounded-full bg-success" />
                {runningCount} online
              </span>
            ) : (
              "No active VMs"
            )
          }
        />
        <DashboardSummaryCard
          title="Active Streams"
          value={String(activeStreamRows.length)}
          visual="streams"
          meta={
            activeStreamRows.length ? (
              <>
                Total monthly burn
                <br />
                {formatToken(totalSpent.monthlyBurn, totalSpent.token)}
              </>
            ) : (
              "No active streams"
            )
          }
        />
        <DashboardSummaryCard
          title="Monthly Spend"
          value={formatToken(totalSpent.tokenValue, totalSpent.token)}
          visual="spend"
          chartData={totalSpent.spendSeries}
          meta={`~ $${totalSpent.usdValue.toFixed(2)} USD`}
        />
      </div>

      <DashboardSection
        title="Active VMs"
        href="/rentals"
        linkLabel="View all VMs"
      >
        {activeVms.length ? (
          <ActiveVmsTable vms={activeVms} />
        ) : (
          <DashboardEmptyState
            icon="vms"
            title="No active VMs"
            description="You don't have any active VMs yet. Rent your first VM to get started."
          />
        )}
      </DashboardSection>

      <DashboardSection
        title="Active Streams"
        href="/streams"
        linkLabel="View all streams"
      >
        {activeStreamRows.length ? (
          <ActiveStreamsTable rows={activeStreamRows} />
        ) : (
          <DashboardEmptyState
            icon="streams"
            title="No active streams"
            description="You don't have any active payment streams yet. Streams provide continuous payment for your running VMs."
          />
        )}
      </DashboardSection>
    </div>
  );
}
