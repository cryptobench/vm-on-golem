"use client";

import React from "react";
import type { Rental } from "../../lib/api";
import { useProjects } from "../../context/ProjectsContext";
import { useProjectRentals } from "../../hooks/useProjectRentals";
import { DashboardSkeleton } from "./DashboardSkeleton";
import { DashboardEmptyState } from "./DashboardEmptyState";
import { DashboardSection } from "./DashboardSection";
import { DashboardSummaryCard } from "./DashboardSummaryCard";
import { ActiveStreamsTable, ActiveVmsTable } from "./DashboardTables";
import { ProjectStartCard } from "./ProjectStartCard";
import { useDashboardStreams } from "./useDashboardStreams";

function formatToken(value: number, token: string, digits = 2) {
  return `${value.toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: value > 0 ? Math.min(2, digits) : 0 })} ${token}`;
}

function isLiveVm(rental: Rental) {
  const status = String(rental.status || "").toLowerCase();
  return status !== "terminated" && status !== "deleted";
}

export function ProjectDashboard() {
  const { activeId, projects } = useProjects();
  const { items } = useProjectRentals(activeId);
  const [mounted, setMounted] = React.useState(false);
  React.useEffect(() => setMounted(true), []);

  const activeProject = projects.find((project) => project.id === activeId);
  const hasSelectedProject = !!activeProject && !(activeProject.id === "default" && activeProject.name === "Default Project");
  const activeRentals = items.filter((rental) => (rental.project_id || "default") === activeId && isLiveVm(rental));
  const activeStreamRentals = activeRentals.filter((rental) => rental.stream_id);
  const runningCount = activeRentals.filter((rental) => String(rental.status).toLowerCase() === "running").length;
  const { rows: streamRows, totalSpent } = useDashboardStreams(activeStreamRentals);

  if (!mounted) return <DashboardSkeleton />;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-text-primary">Dashboard</h1>
        <p className="mt-1 text-sm text-text-secondary">Overview of your resources and spending.</p>
      </div>

      <div className="grid gap-3 lg:grid-cols-3">
        <DashboardSummaryCard
          title="Active VMs"
          value={String(activeRentals.length)}
          visual="vms"
          meta={activeRentals.length ? <span><span className="mr-2 inline-block h-2 w-2 rounded-full bg-success" />{runningCount} Running</span> : "No active VMs"}
        />
        <DashboardSummaryCard
          title="Active Streams"
          value={String(activeStreamRentals.length)}
          visual="streams"
          meta={activeStreamRentals.length ? <>Total monthly burn<br />{formatToken(totalSpent.monthlyBurn, totalSpent.token)}</> : "No active streams"}
        />
        <DashboardSummaryCard
          title="Total Spend (This Month)"
          value={formatToken(totalSpent.tokenValue, totalSpent.token)}
          visual="spend"
          chartData={totalSpent.spendSeries}
          meta={`~ $${totalSpent.usdValue.toFixed(2)} USD`}
        />
      </div>

      <DashboardSection title="Active VMs" href="/rentals" linkLabel="View all VMs">
        {activeRentals.length ? (
          <ActiveVmsTable rentals={activeRentals} />
        ) : (
          <DashboardEmptyState
            icon="vms"
            title="No active VMs"
            description="You don't have any active VMs yet. Rent your first VM to get started."
            actionLabel="Rent a VM"
          />
        )}
      </DashboardSection>

      <DashboardSection title="Active Streams" href="/streams" linkLabel="View all streams">
        {streamRows.length ? (
          <ActiveStreamsTable rows={streamRows} />
        ) : (
          <DashboardEmptyState
            icon="streams"
            title="No active streams"
            description="You don't have any active payment streams yet. Streams provide continuous payment for your running VMs."
          />
        )}
      </DashboardSection>

      <ProjectStartCard hasSelectedProject={hasSelectedProject} />
    </div>
  );
}
