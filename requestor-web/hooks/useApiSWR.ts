"use client";
import useSWR, { SWRConfiguration, mutate as globalMutate } from "swr";
import { useMemo } from "react";
import { useAds } from "../context/AdsContext";
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

// Generic helpers to create tuple keys that include Ads config snapshot
function keyWithAds<T extends any[]>(prefix: string, ads: any, ...parts: T) {
  // We only include a minimal ads snapshot to influence cache separation
  const mode = ads?.mode || "";
  const rpc = ads?.arkiv_rpc_url || "";
  const ws = ads?.arkiv_ws_url || "";
  const chain = ads?.chain_id || "";
  return [prefix, ...parts, mode, rpc, ws, chain] as const;
}

export function useProviderInfo(
  providerId?: string | null,
  config?: SWRConfiguration,
) {
  const { ads } = useAds();
  const key = useMemo(
    () => (providerId ? keyWithAds("provider-info", ads, providerId) : null),
    [providerId, ads],
  );
  return useSWR(key, () => apiProviderInfo(providerId!, ads), {
    revalidateOnFocus: true,
    revalidateOnReconnect: true,
    revalidateIfStale: true,
    ...config,
  });
}

export function useProviderSummary(
  providerId?: string | null,
  config?: SWRConfiguration,
) {
  const { ads } = useAds();
  const key = useMemo(
    () => (providerId ? keyWithAds("provider-summary", ads, providerId) : null),
    [providerId, ads],
  );
  return useSWR(key, () => apiProviderSummary(providerId!, ads), {
    revalidateOnFocus: true,
    revalidateOnReconnect: true,
    revalidateIfStale: true,
    ...config,
  });
}

export function useVmAccess(
  providerId?: string | null,
  vmId?: string | null,
  config?: SWRConfiguration,
) {
  const { ads } = useAds();
  const key = useMemo(
    () =>
      providerId && vmId
        ? keyWithAds("vm-access", ads, providerId, vmId)
        : null,
    [providerId, vmId, ads],
  );
  return useSWR(key, () => apiVmAccess(providerId!, vmId!, ads), {
    revalidateOnFocus: true,
    revalidateOnReconnect: true,
    revalidateIfStale: true,
    ...config,
  });
}

export function useVmCreateJobStatus(
  providerId?: string | null,
  jobId?: string | null,
  config?: SWRConfiguration,
) {
  const { ads } = useAds();
  const key = useMemo(
    () =>
      providerId && jobId
        ? keyWithAds("vm-create-job", ads, providerId, jobId)
        : null,
    [providerId, jobId, ads],
  );
  return useSWR(key, () => apiVmJobStatus(providerId!, jobId!, ads), {
    revalidateOnFocus: true,
    revalidateOnReconnect: true,
    revalidateIfStale: true,
    ...config,
  });
}

export function useVmStatusSafe(
  providerId?: string | null,
  vmId?: string | null,
  config?: SWRConfiguration,
) {
  const { ads } = useAds();
  const key = useMemo(
    () =>
      providerId && vmId
        ? keyWithAds("vm-status-safe", ads, providerId, vmId)
        : null,
    [providerId, vmId, ads],
  );
  return useSWR(key, () => apiVmStatusSafe(providerId!, vmId!, ads), {
    revalidateOnFocus: true,
    revalidateOnReconnect: true,
    revalidateIfStale: true,
    ...config,
  });
}

export function useVmStatus(
  providerId?: string | null,
  vmId?: string | null,
  config?: SWRConfiguration,
) {
  const { ads } = useAds();
  const key = useMemo(
    () =>
      providerId && vmId
        ? keyWithAds("vm-status", ads, providerId, vmId)
        : null,
    [providerId, vmId, ads],
  );
  return useSWR(key, () => apiVmStatus(providerId!, vmId!, ads), {
    revalidateOnFocus: true,
    revalidateOnReconnect: true,
    revalidateIfStale: true,
    ...config,
  });
}

export function useVmStreamStatus(
  providerId?: string | null,
  vmId?: string | null,
  config?: SWRConfiguration,
) {
  const { ads } = useAds();
  const key = useMemo(
    () =>
      providerId && vmId
        ? keyWithAds("vm-stream-status", ads, providerId, vmId)
        : null,
    [providerId, vmId, ads],
  );
  return useSWR(key, () => apiVmStreamStatus(providerId!, vmId!, ads), {
    revalidateOnFocus: true,
    revalidateOnReconnect: true,
    revalidateIfStale: true,
    ...config,
  });
}

export function useVmMetricsLatest(
  providerId?: string | null,
  vmId?: string | null,
  config?: SWRConfiguration,
) {
  const { ads } = useAds();
  const key = useMemo(
    () =>
      providerId && vmId
        ? keyWithAds("vm-metrics-latest", ads, providerId, vmId)
        : null,
    [providerId, vmId, ads],
  );
  return useSWR(key, () => apiVmMetricsLatest(providerId!, vmId!, ads), {
    revalidateOnFocus: true,
    revalidateOnReconnect: true,
    revalidateIfStale: true,
    ...config,
  });
}

export function useVmMetricsHistory(
  providerId?: string | null,
  vmId?: string | null,
  range = "1h",
  config?: SWRConfiguration,
) {
  const { ads } = useAds();
  const key = useMemo(
    () =>
      providerId && vmId
        ? keyWithAds("vm-metrics-history", ads, providerId, vmId, range)
        : null,
    [providerId, vmId, range, ads],
  );
  return useSWR(
    key,
    () => apiVmMetricsHistory(providerId!, vmId!, ads, range),
    {
      revalidateOnFocus: true,
      revalidateOnReconnect: true,
      revalidateIfStale: true,
      ...config,
    },
  );
}

export const mutate = globalMutate;
