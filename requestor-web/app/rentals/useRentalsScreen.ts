"use client";

import React from "react";
import { useProjects } from "../../context/ProjectsContext";
import { useCopySSH } from "../../hooks/useCopySSH";
import { useProjectRentals } from "../../hooks/useProjectRentals";
import { useStreamActions } from "../../hooks/useStreamActions";
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
import { getRequestorRuntimeConfig } from "../../lib/runtimeConfig";
import {
  ensurePaidStreamCanStart,
  terminatePaidRental,
} from "../../lib/rentalLifecycle";

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

export function useRentalsScreen() {
  const [mounted, setMounted] = React.useState(false);
  const [showTerminated, setShowTerminated] = React.useState(false);
  const [query, setQuery] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);
  const [busyId, setBusyId] = React.useState<string | null>(null);
  const streamPaymentAddress = (
    loadSettings().stream_payment_address ||
    getRequestorRuntimeConfig().streamPaymentAddress ||
    ""
  ).trim();
  const { terminate } = useStreamActions(streamPaymentAddress);
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
    } catch (copyError) {
      setError(errorMessage(copyError));
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
        streamPaymentAddress,
      });
      if (String(rental.status || "").toLowerCase() === "suspended") {
        await vmResume(requireProviderEndpoint(rental), rental.vm_id);
      } else {
        await vmStart(requireProviderEndpoint(rental), rental.vm_id);
      }
      updateRentalStatus(rental, "running");
    } catch (startError) {
      setError(errorMessage(startError));
    } finally {
      setBusyId(null);
    }
  };

  const stop = async (rental: Rental) => {
    setError(null);
    setBusyId(rental.vm_id);
    try {
      await vmStop(requireProviderEndpoint(rental), rental.vm_id);
      updateRentalStatus(rental, "stopped");
    } catch (stopError) {
      setError(errorMessage(stopError));
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
        terminateStream: terminate,
        destroyVm: vmDestroy,
      });
      const next = (items || []).map((item) =>
        item.vm_id === rental.vm_id ? terminatedRental : item,
      );
      saveRentals(next);
      setItems(next);
    } catch (destroyError) {
      setError(errorMessage(destroyError));
    } finally {
      setBusyId(null);
    }
  };

  const toggleTerminated = (next: boolean) => {
    setShowTerminated(next);
    saveSettings({ show_terminated: next });
  };

  return {
    active,
    busyId,
    copySSH,
    destroy,
    error,
    hasAnyProjectVm: projectItems.length > 0,
    hasVisibleRows:
      active.length > 0 || (showTerminated && terminated.length > 0),
    mounted,
    query,
    refresh,
    rentalsLoading,
    setQuery,
    showTerminated,
    start,
    stop,
    terminated,
    toggleTerminated,
  };
}

function requireProviderEndpoint(rental: Rental): string {
  if (!rental.provider_endpoint_url) {
    throw new Error("Provider endpoint unavailable");
  }
  return rental.provider_endpoint_url;
}
