"use client";

import { RentalsEmptyState } from "../../components/rentals/RentalsEmptyState";
import { RentalsToolbar } from "../../components/rentals/RentalsToolbar";
import { RentalsTable } from "../../components/rentals/RentalsTable";
import { RentalsTableSkeleton } from "../../components/rentals/RentalsTableSkeleton";
import { PageHeader } from "@golem/ui";
import { useRentalsScreen } from "./useRentalsScreen";

export default function RentalsPage() {
  const screen = useRentalsScreen();

  return (
    <div className="rentals-shell space-y-6">
      <PageHeader
        title="My VMs"
        description="View and manage all virtual machines in your project."
        className="border-b-0 pb-0 xl:items-end"
        actions={
          <RentalsToolbar
            query={screen.query}
            onQueryChange={screen.setQuery}
            showTerminated={screen.showTerminated}
            onShowTerminatedChange={screen.toggleTerminated}
            onRefresh={screen.refresh}
          />
        }
      />

      {!screen.mounted || screen.rentalsLoading ? (
        <RentalsTableSkeleton />
      ) : screen.hasVisibleRows ? (
        <div className="space-y-4">
          {screen.active.length > 0 && (
            <RentalsTable
              title="Active VMs"
              subtitle="Running, stopped, suspended, and provisioning machines."
              count={screen.active.length}
              vms={screen.active}
              timeColumnLabel="Stream Time Left"
            />
          )}
          {screen.showTerminated && screen.terminated.length > 0 && (
            <RentalsTable
              title="Terminated VMs"
              subtitle="These VMs can no longer be started."
              count={screen.terminated.length}
              vms={screen.terminated}
              timeColumnLabel="Terminated At"
              terminated
            />
          )}
        </div>
      ) : (
        <RentalsEmptyState
          title={screen.hasAnyProjectVm ? "No matching VMs" : "No VMs yet"}
          description={
            screen.hasAnyProjectVm
              ? "Try a different search or include terminated VMs."
              : "You don't have any virtual machines in this project."
          }
          showSecondaryAction={screen.hasAnyProjectVm}
          onClearSearch={() => screen.setQuery("")}
        />
      )}
    </div>
  );
}
