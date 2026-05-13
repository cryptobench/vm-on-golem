"use client";

import React from "react";
import {
  loadSettings,
  saveRentals,
  saveSettings,
  type Rental,
  vmDestroy,
  vmResume,
  vmStart,
  vmStop,
} from "../../lib/api";
import {
  ensurePaidStreamCanStart,
  terminatePaidRental,
} from "../../lib/rentalLifecycle";
import { useCopySSH } from "../../hooks/useCopySSH";
import { useStreamActions } from "../../hooks/useStreamActions";
import { useAds } from "../../context/AdsContext";
import { useProjects } from "../../context/ProjectsContext";
import { useProjectRentals } from "../../hooks/useProjectRentals";
import { RentalsEmptyState } from "../../components/rentals/RentalsEmptyState";
import { RentalsToolbar } from "../../components/rentals/RentalsToolbar";
import { RentalsTable } from "../../components/rentals/RentalsTable";
import { RentalsTableSkeleton } from "../../components/rentals/RentalsTableSkeleton";

function isTerminalStatus(status?: string | null) {
  const normalized = String(status || "").toLowerCase();
  return normalized === "terminated" || normalized === "deleted";
}

function matchesQuery(rental: Rental, query: string) {
  const normalized = query.trim().toLowerCase();
  if (!normalized) return true;
  return [
    rental.name,
    rental.vm_id,
    rental.provider_id,
    rental.provider_ip,
    rental.platform,
    rental.stream_id == null ? "" : String(rental.stream_id),
  ]
    .filter(Boolean)
    .some((value) => String(value).toLowerCase().includes(normalized));
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : String(error);
}

export default function RentalsPage() {
  const [mounted, setMounted] = React.useState(false);
  const [showTerminated, setShowTerminated] = React.useState(false);
  const [query, setQuery] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);
  const [busyId, setBusyId] = React.useState<string | null>(null);
  const { ads } = useAds();
  const spAddr = (
    loadSettings().stream_payment_address ||
    process.env.NEXT_PUBLIC_STREAM_PAYMENT_ADDRESS ||
    ""
  ).trim();
  const { terminate } = useStreamActions(spAddr);
  const { activeId } = useProjects();
  const {
    items,
    isInitialLoading: rentalsLoading,
    setItems,
    refresh,
  } = useProjectRentals(activeId);
  const copySSHAction = useCopySSH();

  React.useEffect(() => {
    setMounted(true);
  }, []);

  React.useEffect(() => {
    if (!mounted) return;
    setShowTerminated(!!loadSettings().show_terminated);

    const onSettings = (event: Event) => {
      const settings = (event as CustomEvent).detail || loadSettings();
      setShowTerminated(!!settings.show_terminated);
    };
    const onStorage = () => setShowTerminated(!!loadSettings().show_terminated);

    window.addEventListener("requestor_settings_changed", onSettings);
    window.addEventListener("storage", onStorage);
    return () => {
      window.removeEventListener("requestor_settings_changed", onSettings);
      window.removeEventListener("storage", onStorage);
    };
  }, [mounted]);

  React.useEffect(() => {
    if (!mounted) return;
    const timer = window.setTimeout(() => refresh(), 200);
    return () => window.clearTimeout(timer);
  }, [mounted, refresh]);

  const projectItems = React.useMemo(
    () =>
      (items || []).filter(
        (item) => (item.project_id || "default") === activeId,
      ) as Rental[],
    [activeId, items],
  );

  const active = React.useMemo(
    () =>
      projectItems.filter(
        (rental) =>
          !isTerminalStatus(rental.status) && matchesQuery(rental, query),
      ),
    [projectItems, query],
  );
  const terminated = React.useMemo(
    () =>
      projectItems.filter(
        (rental) =>
          isTerminalStatus(rental.status) && matchesQuery(rental, query),
      ),
    [projectItems, query],
  );

  const copySSH = async (rental: Rental) => {
    setError(null);
    setBusyId(rental.vm_id);
    try {
      await copySSHAction(rental);
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusyId(null);
    }
  };

  const updateRentalStatus = (rental: Rental, status: string) => {
    const next = (items || []).map((item) =>
      item.vm_id === rental.vm_id ? { ...item, status } : item,
    );
    saveRentals(next);
    setItems(next);
  };

  const start = async (rental: Rental) => {
    setError(null);
    setBusyId(rental.vm_id);
    try {
      await ensurePaidStreamCanStart({
        rental,
        streamPaymentAddress: spAddr,
      });
      if (String(rental.status || "").toLowerCase() === "suspended") {
        await vmResume(rental.provider_id, rental.vm_id, ads);
      } else {
        await vmStart(rental.provider_id, rental.vm_id, ads);
      }
      updateRentalStatus(rental, "running");
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusyId(null);
    }
  };

  const stop = async (rental: Rental) => {
    setError(null);
    setBusyId(rental.vm_id);
    try {
      await vmStop(rental.provider_id, rental.vm_id, ads);
      updateRentalStatus(rental, "stopped");
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusyId(null);
    }
  };

  const destroy = async (rental: Rental) => {
    setError(null);
    setBusyId(rental.vm_id);
    try {
      const terminatedRental = await terminatePaidRental({
        rental,
        ads,
        terminateStream: terminate,
        destroyVm: vmDestroy,
      });
      const next = (items || []).map((item) =>
        item.vm_id === rental.vm_id ? terminatedRental : item,
      );
      saveRentals(next);
      setItems(next);
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusyId(null);
    }
  };

  const toggleTerminated = (next: boolean) => {
    setShowTerminated(next);
    saveSettings({ show_terminated: next });
  };

  const hasAnyProjectVm = projectItems.length > 0;
  const hasVisibleRows =
    active.length > 0 || (showTerminated && terminated.length > 0);

  return (
    <div className="rentals-shell space-y-6">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <h1>My VMs</h1>
          <p className="mt-2 text-sm text-text-secondary">
            View and manage all virtual machines in your project.
          </p>
        </div>
        <RentalsToolbar
          query={query}
          onQueryChange={setQuery}
          showTerminated={showTerminated}
          onShowTerminatedChange={toggleTerminated}
          onRefresh={refresh}
        />
      </div>

      {error && (
        <div className="rounded-lg border border-danger bg-danger-soft px-4 py-3 text-sm text-danger">
          {error}
        </div>
      )}

      {!mounted || rentalsLoading ? (
        <RentalsTableSkeleton />
      ) : hasVisibleRows ? (
        <div className="space-y-4">
          {active.length > 0 && (
            <RentalsTable
              title="Active VMs"
              subtitle="Running, stopped, suspended, and provisioning machines."
              count={active.length}
              rentals={active}
              busyId={busyId}
              timeColumnLabel="Stream Time Left"
              onCopySSH={copySSH}
              onStart={start}
              onStop={stop}
              onDestroy={destroy}
            />
          )}
          {showTerminated && terminated.length > 0 && (
            <RentalsTable
              title="Terminated VMs"
              subtitle="These VMs can no longer be started."
              count={terminated.length}
              rentals={terminated}
              busyId={busyId}
              timeColumnLabel="Terminated At"
              terminated
              onDestroy={destroy}
            />
          )}
        </div>
      ) : (
        <RentalsEmptyState
          title={hasAnyProjectVm ? "No matching VMs" : "No VMs yet"}
          description={
            hasAnyProjectVm
              ? "Try a different search or include terminated VMs."
              : "You don't have any virtual machines in this project."
          }
          showSecondaryAction={hasAnyProjectVm}
          onClearSearch={() => setQuery("")}
        />
      )}
    </div>
  );
}
