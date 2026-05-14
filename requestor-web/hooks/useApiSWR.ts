"use client";
import useSWR, { SWRConfiguration, mutate as globalMutate } from "swr";
import { useMemo } from "react";
import {
  providerInfo as apiProviderInfo,
  providerSummary as apiProviderSummary,
  vmAccess as apiVmAccess,
  vmJobStatus as apiVmJobStatus,
  vmStatusSafe as apiVmStatusSafe,
  vmStatus as apiVmStatus,
  vmStreamStatus as apiVmStreamStatus,
  vmMetricsLatest as apiVmMetricsLatest,
  vmMetricsHistory as apiVmMetricsHistory,
} from "../lib/api";

function providerKey<T extends any[]>(
  prefix: string,
  providerEndpointUrl: string | null | undefined,
  ...parts: T
) {
  return providerEndpointUrl
    ? ([prefix, providerEndpointUrl, ...parts] as const)
    : null;
}

export function useProviderInfo(
  providerEndpointUrl?: string | null,
  config?: SWRConfiguration,
) {
  const key = useMemo(
    () => providerKey("provider-info", providerEndpointUrl),
    [providerEndpointUrl],
  );
  return useSWR(key, () => apiProviderInfo(providerEndpointUrl!), {
    revalidateOnFocus: true,
    revalidateOnReconnect: true,
    revalidateIfStale: true,
    ...config,
  });
}

export function useProviderSummary(
  providerEndpointUrl?: string | null,
  config?: SWRConfiguration,
) {
  const key = useMemo(
    () => providerKey("provider-summary", providerEndpointUrl),
    [providerEndpointUrl],
  );
  return useSWR(key, () => apiProviderSummary(providerEndpointUrl!), {
    revalidateOnFocus: true,
    revalidateOnReconnect: true,
    revalidateIfStale: true,
    ...config,
  });
}

export function useVmAccess(
  providerEndpointUrl?: string | null,
  vmId?: string | null,
  config?: SWRConfiguration,
) {
  const key = useMemo(
    () =>
      providerEndpointUrl && vmId
        ? providerKey("vm-access", providerEndpointUrl, vmId)
        : null,
    [providerEndpointUrl, vmId],
  );
  return useSWR(key, () => apiVmAccess(providerEndpointUrl!, vmId!), {
    revalidateOnFocus: true,
    revalidateOnReconnect: true,
    revalidateIfStale: true,
    ...config,
  });
}

export function useVmCreateJobStatus(
  providerEndpointUrl?: string | null,
  jobId?: string | null,
  config?: SWRConfiguration,
) {
  const key = useMemo(
    () =>
      providerEndpointUrl && jobId
        ? providerKey("vm-create-job", providerEndpointUrl, jobId)
        : null,
    [providerEndpointUrl, jobId],
  );
  return useSWR(key, () => apiVmJobStatus(providerEndpointUrl!, jobId!), {
    revalidateOnFocus: true,
    revalidateOnReconnect: true,
    revalidateIfStale: true,
    ...config,
  });
}

export function useVmStatusSafe(
  providerEndpointUrl?: string | null,
  vmId?: string | null,
  config?: SWRConfiguration,
) {
  const key = useMemo(
    () =>
      providerEndpointUrl && vmId
        ? providerKey("vm-status-safe", providerEndpointUrl, vmId)
        : null,
    [providerEndpointUrl, vmId],
  );
  return useSWR(key, () => apiVmStatusSafe(providerEndpointUrl!, vmId!), {
    revalidateOnFocus: true,
    revalidateOnReconnect: true,
    revalidateIfStale: true,
    ...config,
  });
}

export function useVmStatus(
  providerEndpointUrl?: string | null,
  vmId?: string | null,
  config?: SWRConfiguration,
) {
  const key = useMemo(
    () =>
      providerEndpointUrl && vmId
        ? providerKey("vm-status", providerEndpointUrl, vmId)
        : null,
    [providerEndpointUrl, vmId],
  );
  return useSWR(key, () => apiVmStatus(providerEndpointUrl!, vmId!), {
    revalidateOnFocus: true,
    revalidateOnReconnect: true,
    revalidateIfStale: true,
    ...config,
  });
}

export function useVmStreamStatus(
  providerEndpointUrl?: string | null,
  vmId?: string | null,
  config?: SWRConfiguration,
) {
  const key = useMemo(
    () =>
      providerEndpointUrl && vmId
        ? providerKey("vm-stream-status", providerEndpointUrl, vmId)
        : null,
    [providerEndpointUrl, vmId],
  );
  return useSWR(key, () => apiVmStreamStatus(providerEndpointUrl!, vmId!), {
    revalidateOnFocus: true,
    revalidateOnReconnect: true,
    revalidateIfStale: true,
    ...config,
  });
}

export function useVmMetricsLatest(
  providerEndpointUrl?: string | null,
  vmId?: string | null,
  config?: SWRConfiguration,
) {
  const key = useMemo(
    () =>
      providerEndpointUrl && vmId
        ? providerKey("vm-metrics-latest", providerEndpointUrl, vmId)
        : null,
    [providerEndpointUrl, vmId],
  );
  return useSWR(key, () => apiVmMetricsLatest(providerEndpointUrl!, vmId!), {
    revalidateOnFocus: true,
    revalidateOnReconnect: true,
    revalidateIfStale: true,
    ...config,
  });
}

export function useVmMetricsHistory(
  providerEndpointUrl?: string | null,
  vmId?: string | null,
  range = "1h",
  config?: SWRConfiguration,
) {
  const key = useMemo(
    () =>
      providerEndpointUrl && vmId
        ? providerKey("vm-metrics-history", providerEndpointUrl, vmId, range)
        : null,
    [providerEndpointUrl, vmId, range],
  );
  return useSWR(
    key,
    () => apiVmMetricsHistory(providerEndpointUrl!, vmId!, range),
    {
      revalidateOnFocus: true,
      revalidateOnReconnect: true,
      revalidateIfStale: true,
      ...config,
    },
  );
}

export const mutate = globalMutate;
