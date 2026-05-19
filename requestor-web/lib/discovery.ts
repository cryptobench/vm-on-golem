"use client";

import {
  filterProvidersWithUsableEndpoint,
  type ProviderAd,
} from "./api";

export const DISCOVERY_RECONNECT_INITIAL_DELAY_MS = 1000;
export const DISCOVERY_RECONNECT_MAX_DELAY_MS = 10000;

export type DiscoveryFilters = Partial<{
  cpu: number;
  memory: number;
  storage: number;
  country: string;
  platform: string;
}>;

export type DiscoveryEvent =
  | { type: "snapshot"; advertisements: ProviderAd[] }
  | { type: "provider.upsert"; advertisement: ProviderAd }
  | { type: "provider.remove"; provider_id: string }
  | { type: "error"; error: string }
  | { type: "hello" | "heartbeat"; [key: string]: unknown };

export function subscribeMessage(filters: DiscoveryFilters) {
  return {
    type: "subscribe",
    filters: cleanFilters(filters),
  };
}

export function applyDiscoveryEvent(
  rows: ProviderAd[],
  event: DiscoveryEvent,
): ProviderAd[] {
  if (event.type === "snapshot") {
    return filterProvidersWithUsableEndpoint(event.advertisements);
  }
  if (event.type === "provider.upsert") {
    if (!filterProvidersWithUsableEndpoint([event.advertisement]).length) {
      return rows.filter(
        (provider) => provider.provider_id !== event.advertisement.provider_id,
      );
    }
    const next = rows.filter(
      (provider) => provider.provider_id !== event.advertisement.provider_id,
    );
    return [...next, event.advertisement];
  }
  if (event.type === "provider.remove") {
    return rows.filter((provider) => provider.provider_id !== event.provider_id);
  }
  return rows;
}

export function countriesFromProviders(providers: ProviderAd[]): string[] {
  return Array.from(
    new Set(
      providers
        .map((provider) => provider.country)
        .filter(Boolean)
        .map((country) => String(country).toUpperCase()),
    ),
  ).sort();
}

export function nextDiscoveryReconnectDelayMs(
  currentDelayMs: number,
): number {
  return Math.min(currentDelayMs * 2, DISCOVERY_RECONNECT_MAX_DELAY_MS);
}

function cleanFilters(filters: DiscoveryFilters): DiscoveryFilters {
  const next: DiscoveryFilters = {};
  if (filters.cpu != null) next.cpu = filters.cpu;
  if (filters.memory != null) next.memory = filters.memory;
  if (filters.storage != null) next.storage = filters.storage;
  if (filters.country) next.country = filters.country;
  if (filters.platform) next.platform = filters.platform;
  return next;
}
