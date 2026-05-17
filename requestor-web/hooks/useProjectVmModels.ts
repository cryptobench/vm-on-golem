"use client";

import React from "react";
import useSWR from "swr";
import {
  providerInfo,
  type Rental,
  vmAccess,
  vmStatusSafe,
  vmStreamStatus,
} from "../lib/api";
import {
  buildRequestorVmModel,
  isTerminalVmStatus,
  type RequestorVmModel,
  type RequestorVmProbe,
  type VmSafeStatus,
} from "../lib/requestorVmModel";
import { reconcileProviderMissingRentals } from "../lib/rentalReconciliation";
import { useProjectRentals } from "./useProjectRentals";

type ProbeResult<T> = { ok: true; value: T } | { ok: false; error: unknown };

export function useProjectVmModels(projectId: string) {
  const {
    items: rentalItems,
    isInitialLoading: rentalsLoading,
    setItems,
    refresh: refreshRentals,
  } = useProjectRentals(projectId);
  const projectRentals = React.useMemo(
    () =>
      rentalItems.filter(
        (rental) => (rental.project_id || "default") === projectId,
      ) as Rental[],
    [projectId, rentalItems],
  );
  const probeKey = React.useMemo(
    () =>
      projectRentals.length
        ? [
            "requestor-vm-model-probes",
            projectId,
            projectRentals.map(rentalProbeKey).join("|"),
          ]
        : null,
    [projectId, projectRentals],
  );
  const {
    data: probes,
    isValidating,
    mutate,
  } = useSWR(probeKey, () => loadVmProbes(projectRentals), {
    refreshInterval: 8000,
    revalidateOnFocus: true,
    revalidateOnReconnect: true,
  });
  const items = React.useMemo<RequestorVmModel[]>(
    () =>
      projectRentals.map((rental) =>
        buildRequestorVmModel(rental, probes?.[rental.vm_id]),
      ),
    [probes, projectRentals],
  );
  React.useEffect(() => {
    if (!probes) return;
    const statuses = Object.fromEntries(
      Object.entries(probes).map(([vmId, probe]) => [vmId, probe.safeStatus]),
    );
    const result = reconcileProviderMissingRentals(
      rentalItems,
      statuses,
      projectId,
    );
    if (!result.changed) return;
    setItems(result.rentals);
  }, [probes, projectId, rentalItems, setItems]);

  const refresh = React.useCallback(async () => {
    refreshRentals();
    await mutate();
  }, [mutate, refreshRentals]);
  const isInitialLoading =
    rentalsLoading || (projectRentals.length > 0 && !probes && isValidating);

  return {
    setItems,
    items,
    projectRentals,
    rawItems: rentalItems,
    isInitialLoading,
    refresh,
  } as const;
}

async function loadVmProbes(rentals: Rental[]) {
  const pairs = await Promise.all(
    rentals.map(async (rental) => [rental.vm_id, await loadVmProbe(rental)]),
  );
  return Object.fromEntries(pairs) as Record<string, RequestorVmProbe>;
}

async function loadVmProbe(rental: Rental): Promise<RequestorVmProbe> {
  if (
    isTerminalVmStatus(rental.status) ||
    !rental.provider_endpoint_url ||
    !rental.vm_id
  ) {
    return emptyProbe();
  }

  const [provider, safeStatus, access, stream] = await Promise.all([
    resolveProbe(providerInfo(rental.provider_endpoint_url)),
    resolveProbe(vmStatusSafe(rental.provider_endpoint_url, rental.vm_id)),
    resolveProbe(vmAccess(rental.provider_endpoint_url, rental.vm_id)),
    rental.stream_id
      ? resolveProbe(vmStreamStatus(rental.provider_endpoint_url, rental.vm_id))
      : Promise.resolve(null),
  ]);

  return {
    provider: provider?.ok ? asRecord(provider.value) : null,
    providerError: provider && !provider.ok ? provider.error : null,
    safeStatus: safeStatus?.ok
      ? normalizeSafeStatus(safeStatus.value)
      : safeStatusError(safeStatus?.error),
    access: access?.ok ? asRecord(access.value) : null,
    accessError: access && !access.ok ? access.error : null,
    stream: stream?.ok ? asRecord(stream.value) : null,
    streamError: stream && !stream.ok ? stream.error : null,
  };
}

function emptyProbe(): RequestorVmProbe {
  return {
    provider: null,
    providerError: null,
    safeStatus: null,
    access: null,
    accessError: null,
    stream: null,
    streamError: null,
  };
}

async function resolveProbe<T>(promise: Promise<T>): Promise<ProbeResult<T>> {
  try {
    return { ok: true, value: await promise };
  } catch (error) {
    return { ok: false, error };
  }
}

function normalizeSafeStatus(value: unknown): VmSafeStatus {
  const status = value as {
    exists?: boolean;
    data?: unknown;
    code?: number;
    error?: string;
  };
  if (status.exists) {
    return { exists: true, data: asRecord(status.data) || {} };
  }
  return {
    exists: false,
    code: Number(status.code || 0),
    error: status.error || "Provider status unavailable",
  };
}

function safeStatusError(error: unknown): VmSafeStatus {
  return {
    exists: false,
    code: Number((error as { status?: number } | null)?.status || 0),
    error: error instanceof Error ? error.message : String(error),
  };
}

function asRecord(value: unknown) {
  return value && typeof value === "object"
    ? (value as Record<string, unknown>)
    : null;
}

function rentalProbeKey(rental: Rental) {
  return [
    rental.vm_id,
    rental.provider_endpoint_url || "",
    rental.status || "",
    rental.stream_id || "",
    rental.creation_job_id || "",
  ].join(":");
}
