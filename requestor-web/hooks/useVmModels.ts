"use client";

import React from "react";
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
import { useRentals } from "./useRentals";

type ProbeResult<T> = { ok: true; value: T } | { ok: false; error: unknown };

export function useVmModels() {
  const [probes, setProbes] = React.useState<
    Record<string, RequestorVmProbe>
  >({});
  const [pendingProbeIds, setPendingProbeIds] = React.useState<
    Record<string, boolean>
  >({});
  const [refreshNonce, setRefreshNonce] = React.useState(0);
  const probesRef = React.useRef(probes);
  const latestProbeKeysRef = React.useRef<Record<string, string>>({});
  const {
    items: rentalItems,
    isInitialLoading: rentalsLoading,
    setItems,
    refresh: refreshRentals,
  } = useRentals();
  const rentals = rentalItems as Rental[];
  const probeKey = React.useMemo(
    () =>
      rentals.length
        ? [
            "requestor-vm-model-probes",
            rentals.map(rentalProbeKey).join("|"),
          ]
        : null,
    [rentals],
  );

  React.useEffect(() => {
    probesRef.current = probes;
  }, [probes]);

  React.useEffect(() => {
    const activeVmIds = new Set(rentals.map((rental) => rental.vm_id));
    const nextProbeKeys = Object.fromEntries(
      rentals.map((rental) => [rental.vm_id, rentalProbeKey(rental)]),
    );
    latestProbeKeysRef.current = nextProbeKeys;
    setProbes((current) => filterByVmIds(current, activeVmIds));
    setPendingProbeIds((current) => filterByVmIds(current, activeVmIds));
  }, [probeKey, rentals]);

  React.useEffect(() => {
    if (!rentals.length) return;

    let cancelled = false;
    let timer: number | null = null;

    const loadAll = () => {
      for (const rental of rentals) {
        const vmId = rental.vm_id;
        const currentKey = rentalProbeKey(rental);
        latestProbeKeysRef.current[vmId] = currentKey;

        if (
          isTerminalVmStatus(rental.status) ||
          !rental.provider_endpoint_url ||
          !vmId
        ) {
          setProbes((current) => ({ ...current, [vmId]: emptyProbe() }));
          setPendingProbeIds((current) => omitVmId(current, vmId));
          continue;
        }

        if (!probesRef.current[vmId]) {
          setPendingProbeIds((current) => ({ ...current, [vmId]: true }));
        }

        void loadVmProbe(rental).then(
          (probe) => {
            if (
              cancelled ||
              latestProbeKeysRef.current[vmId] !== currentKey
            ) {
              return;
            }
            setProbes((current) => ({ ...current, [vmId]: probe }));
            setPendingProbeIds((current) => omitVmId(current, vmId));
          },
          (error) => {
            if (
              cancelled ||
              latestProbeKeysRef.current[vmId] !== currentKey
            ) {
              return;
            }
            setProbes((current) => ({
              ...current,
              [vmId]: failedProbe(error, !!rental.stream_id),
            }));
            setPendingProbeIds((current) => omitVmId(current, vmId));
          },
        );
      }
    };

    loadAll();
    timer = window.setInterval(loadAll, 8000);
    return () => {
      cancelled = true;
      if (timer != null) window.clearInterval(timer);
    };
  }, [probeKey, rentals, refreshNonce]);

  React.useEffect(() => {
    const refreshProbes = () => setRefreshNonce((current) => current + 1);
    window.addEventListener("focus", refreshProbes);
    window.addEventListener("online", refreshProbes);
    return () => {
      window.removeEventListener("focus", refreshProbes);
      window.removeEventListener("online", refreshProbes);
    };
  }, []);

  const items = React.useMemo<RequestorVmModel[]>(
    () =>
      rentals.map((rental) =>
        buildRequestorVmModel(rental, probes[rental.vm_id], {
          probePending: !!pendingProbeIds[rental.vm_id],
        }),
      ),
    [pendingProbeIds, probes, rentals],
  );
  React.useEffect(() => {
    if (!probes) return;
    const statuses = Object.fromEntries(
      Object.entries(probes).map(([vmId, probe]) => [vmId, probe.safeStatus]),
    );
    const result = reconcileProviderMissingRentals(rentalItems, statuses);
    if (!result.changed) return;
    setItems(result.rentals);
  }, [probes, rentalItems, setItems]);

  const refresh = React.useCallback(async () => {
    refreshRentals();
    setRefreshNonce((current) => current + 1);
  }, [refreshRentals]);
  const isInitialLoading = rentalsLoading;

  return {
    setItems,
    items,
    rentals,
    rawItems: rentalItems,
    isInitialLoading,
    refresh,
  } as const;
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

function failedProbe(error: unknown, hasStream: boolean): RequestorVmProbe {
  return {
    provider: null,
    providerError: error,
    safeStatus: safeStatusError(error),
    access: null,
    accessError: error,
    stream: null,
    streamError: hasStream ? error : null,
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

function filterByVmIds<T>(
  values: Record<string, T>,
  vmIds: Set<string>,
): Record<string, T> {
  return Object.fromEntries(
    Object.entries(values).filter(([vmId]) => vmIds.has(vmId)),
  );
}

function omitVmId<T>(values: Record<string, T>, vmId: string): Record<string, T> {
  if (!(vmId in values)) return values;
  const next = { ...values };
  delete next[vmId];
  return next;
}
