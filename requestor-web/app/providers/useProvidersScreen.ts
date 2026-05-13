"use client";

import React from "react";
import { computeEstimate, fetchProviders, type ProviderAd } from "../../lib/api";
import { useAds } from "../../context/AdsContext";
import { useSettings } from "../../hooks/useSettings";
import {
  estimateSpec,
  providerMatchesSearch,
  providerPlatform,
} from "../../components/providers/providerDisplay";
import type { ProviderFilters } from "../../components/providers/ProviderFiltersPanel";

export const PROVIDERS_PAGE_SIZE = 10;

export const EMPTY_PROVIDER_FILTERS: ProviderFilters = {
  search: "",
  country: "",
  platform: "",
};

export function providerCountLabel(count: number) {
  return `${count} provider${count === 1 ? "" : "s"}`;
}

export function useProvidersScreen() {
  const { ads } = useAds();
  const { displayCurrency, setDisplayCurrency } = useSettings();
  const [filters, setFilters] = React.useState<ProviderFilters>(readFiltersFromUrl);
  const [countries, setCountries] = React.useState<string[]>([]);
  const [loadingCountries, setLoadingCountries] = React.useState(false);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [rows, setRows] = React.useState<ProviderAd[]>([]);
  const [page, setPage] = React.useState(1);
  const [filtersOpen, setFiltersOpen] = React.useState(false);
  const [filtersMounted, setFiltersMounted] = React.useState(false);
  const [selectedProvider, setSelectedProvider] = React.useState<ProviderAd | null>(null);
  const closeTimerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);

  const spec = estimateSpec(filters);
  const showTokenPrices = displayCurrency === "token";
  const pageCount = Math.max(1, Math.ceil(rows.length / PROVIDERS_PAGE_SIZE));
  const visibleRows = rows.slice(
    (page - 1) * PROVIDERS_PAGE_SIZE,
    page * PROVIDERS_PAGE_SIZE,
  );

  const loadProviders = React.useCallback(
    async (nextFilters = filters) => {
      setLoading(true);
      setError(null);
      try {
        const query = {
          cpu: nextFilters.cpu,
          memory: nextFilters.memory,
          storage: nextFilters.storage,
          country: nextFilters.country || undefined,
        };
        const data = await fetchProviders(query, ads);
        const nextSpec = estimateSpec(nextFilters);
        setRows(applyClientFilters(data, nextFilters, nextSpec));
        setPage(1);
        writeFiltersToUrl(nextFilters);
      } catch (event) {
        setError(event instanceof Error ? event.message : String(event));
      } finally {
        setLoading(false);
      }
    },
    [ads, filters],
  );

  React.useEffect(() => {
    let cancelled = false;
    async function loadCountries() {
      setLoadingCountries(true);
      try {
        const { listCountries } = await import("../../lib/providers");
        const list = await listCountries(ads);
        if (!cancelled) setCountries(list);
      } catch {
        if (!cancelled) setCountries([]);
      } finally {
        if (!cancelled) setLoadingCountries(false);
      }
    }
    loadCountries();
    return () => {
      cancelled = true;
    };
  }, [ads]);

  React.useEffect(() => {
    try {
      const raw = localStorage.getItem("requestor_pending_create");
      if (!raw) {
        loadProviders(filters);
        return;
      }
      const pending = JSON.parse(raw);
      const next = {
        ...filters,
        cpu: pending.cpu != null ? Number(pending.cpu) : filters.cpu,
        memory: pending.memory != null ? Number(pending.memory) : filters.memory,
        storage: pending.storage != null ? Number(pending.storage) : filters.storage,
        country: Array.isArray(pending.countries) ? "" : pending.country || filters.country,
        maxUsd: pending.max_usd_per_month != null
          ? Number(pending.max_usd_per_month)
          : filters.maxUsd,
      };
      localStorage.removeItem("requestor_pending_create");
      setFilters(next);
      loadProviders(next);
    } catch {
      loadProviders(filters);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  React.useEffect(() => {
    if (!rows.length) return;
    const pageMax = Math.max(1, Math.ceil(rows.length / PROVIDERS_PAGE_SIZE));
    if (page > pageMax) setPage(pageMax);
  }, [page, rows.length]);

  React.useEffect(() => {
    return () => {
      if (closeTimerRef.current) clearTimeout(closeTimerRef.current);
    };
  }, []);

  const openFilters = () => {
    if (closeTimerRef.current) clearTimeout(closeTimerRef.current);
    setFiltersMounted(true);
    requestAnimationFrame(() => setFiltersOpen(true));
  };

  const closeFilters = () => {
    setFiltersOpen(false);
    if (closeTimerRef.current) clearTimeout(closeTimerRef.current);
    closeTimerRef.current = setTimeout(() => {
      setFiltersMounted(false);
    }, 220);
  };

  const resetFilters = () => {
    setFilters(EMPTY_PROVIDER_FILTERS);
    loadProviders(EMPTY_PROVIDER_FILTERS);
  };

  const toggleCurrency = () => {
    setDisplayCurrency(showTokenPrices ? "fiat" : "token");
  };

  return {
    ads,
    filters,
    setFilters,
    countries,
    loadingCountries,
    loading,
    error,
    rows,
    page,
    setPage,
    filtersOpen,
    filtersMounted,
    selectedProvider,
    setSelectedProvider,
    spec,
    showTokenPrices,
    pageCount,
    visibleRows,
    openFilters,
    closeFilters,
    resetFilters,
    loadProviders,
    toggleCurrency,
    setDisplayCurrency,
  };
}

function parseNumber(value: string | null) {
  if (value == null || value === "") return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function readFiltersFromUrl(): ProviderFilters {
  if (typeof window === "undefined") return EMPTY_PROVIDER_FILTERS;
  const params = new URLSearchParams(window.location.search);
  return {
    search: params.get("q") || "",
    country: params.get("country") || "",
    platform: params.get("platform") || "",
    cpu: parseNumber(params.get("cpu")),
    memory: parseNumber(params.get("memory")),
    storage: parseNumber(params.get("storage")),
    maxUsd: parseNumber(params.get("max_usd")),
  };
}

function writeFiltersToUrl(filters: ProviderFilters) {
  const params = new URLSearchParams();
  const set = (key: string, value?: string | number) => {
    if (value != null && String(value) !== "") params.set(key, String(value));
  };
  set("q", filters.search);
  set("country", filters.country);
  set("platform", filters.platform);
  set("cpu", filters.cpu);
  set("memory", filters.memory);
  set("storage", filters.storage);
  set("max_usd", filters.maxUsd);
  const query = params.toString();
  window.history.replaceState(null, "", query ? `/providers?${query}` : "/providers");
}

function applyClientFilters(
  providers: ProviderAd[],
  filters: ProviderFilters,
  spec: ReturnType<typeof estimateSpec>,
) {
  return providers.filter((provider) => {
    if (!providerMatchesSearch(provider, filters.search)) return false;
    if (filters.platform && providerPlatform(provider).toLowerCase() !== filters.platform) return false;
    if (filters.maxUsd != null) {
      const estimate = computeEstimate(provider, spec.cpu, spec.memory, spec.storage);
      if (estimate.usd_per_month > filters.maxUsd) return false;
    }
    return true;
  });
}
