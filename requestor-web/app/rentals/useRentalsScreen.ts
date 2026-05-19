"use client";

import React from "react";
import { useProjects } from "../../context/ProjectsContext";
import { useProjectVmModels } from "../../hooks/useProjectVmModels";
import {
  loadSettings,
  saveSettings,
} from "../../lib/api";
import {
  isTerminalVmStatus,
  type RequestorVmModel,
} from "../../lib/requestorVmModel";

function matchesQuery(vm: RequestorVmModel, query: string) {
  const { rental } = vm;
  const normalized = query.trim().toLowerCase();
  if (!normalized) return true;
  return [
    rental.name,
    rental.vm_id,
    rental.provider_id,
    rental.provider_ip,
    vm.platform,
    rental.stream_id == null ? "" : String(rental.stream_id),
  ]
    .filter(Boolean)
    .some((value) => String(value).toLowerCase().includes(normalized));
}

export function useRentalsScreen() {
  const [mounted, setMounted] = React.useState(false);
  const [showTerminated, setShowTerminated] = React.useState(false);
  const [query, setQuery] = React.useState("");
  const { activeId } = useProjects();
  const {
    items,
    projectRentals,
    isInitialLoading: rentalsLoading,
    refresh,
  } = useProjectVmModels(activeId);

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

  const active = React.useMemo(
    () =>
      items.filter(
        (vm) =>
          !isTerminalVmStatus(vm.lifecycle.status) && matchesQuery(vm, query),
      ),
    [items, query],
  );
  const terminated = React.useMemo(
    () =>
      items.filter(
        (vm) =>
          isTerminalVmStatus(vm.lifecycle.status) && matchesQuery(vm, query),
      ),
    [items, query],
  );

  const toggleTerminated = (next: boolean) => {
    setShowTerminated(next);
    saveSettings({ show_terminated: next });
  };

  return {
    active,
    hasAnyProjectVm: projectRentals.length > 0,
    hasVisibleRows:
      active.length > 0 || (showTerminated && terminated.length > 0),
    mounted,
    query,
    refresh,
    rentalsLoading,
    setQuery,
    showTerminated,
    terminated,
    toggleTerminated,
  };
}
