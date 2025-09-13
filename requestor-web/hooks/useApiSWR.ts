"use client";
import useSWR, { SWRConfiguration, mutate as globalMutate } from "swr";
import { useMemo } from "react";
import { useAds } from "../context/AdsContext";
import {
  providerInfo as apiProviderInfo,
  vmAccess as apiVmAccess,
  vmStatusSafe as apiVmStatusSafe,
  vmStatus as apiVmStatus,
  vmStreamStatus as apiVmStreamStatus,
} from "../lib/api";

// Generic helpers to create tuple keys that include Ads config snapshot
function keyWithAds<T extends any[]>(prefix: string, ads: any, ...parts: T) {
  // We only include a minimal ads snapshot to influence cache separation
  const mode = ads?.mode || "";
  const rpc = ads?.golem_base_rpc_url || "";
  const ws = ads?.golem_base_ws_url || "";
  const chain = ads?.chain_id || "";
  return [prefix, ...parts, mode, rpc, ws, chain] as const;
}

export function useProviderInfo(providerId?: string | null, config?: SWRConfiguration) {
  const { ads } = useAds();
  const key = useMemo(() => (providerId ? keyWithAds("provider-info", ads, providerId) : null), [providerId, ads]);
  return useSWR(key, () => apiProviderInfo(providerId!, ads), config);
}

export function useVmAccess(providerId?: string | null, vmId?: string | null, config?: SWRConfiguration) {
  const { ads } = useAds();
  const key = useMemo(() => ((providerId && vmId) ? keyWithAds("vm-access", ads, providerId, vmId) : null), [providerId, vmId, ads]);
  return useSWR(key, () => apiVmAccess(providerId!, vmId!, ads), config);
}

export function useVmStatusSafe(providerId?: string | null, vmId?: string | null, config?: SWRConfiguration) {
  const { ads } = useAds();
  const key = useMemo(() => ((providerId && vmId) ? keyWithAds("vm-status-safe", ads, providerId, vmId) : null), [providerId, vmId, ads]);
  return useSWR(key, () => apiVmStatusSafe(providerId!, vmId!, ads), config);
}

export function useVmStatus(providerId?: string | null, vmId?: string | null, config?: SWRConfiguration) {
  const { ads } = useAds();
  const key = useMemo(() => ((providerId && vmId) ? keyWithAds("vm-status", ads, providerId, vmId) : null), [providerId, vmId, ads]);
  return useSWR(key, () => apiVmStatus(providerId!, vmId!, ads), config);
}

export function useVmStreamStatus(providerId?: string | null, vmId?: string | null, config?: SWRConfiguration) {
  const { ads } = useAds();
  const key = useMemo(() => ((providerId && vmId) ? keyWithAds("vm-stream-status", ads, providerId, vmId) : null), [providerId, vmId, ads]);
  return useSWR(key, () => apiVmStreamStatus(providerId!, vmId!, ads), config);
}

export const mutate = globalMutate;
