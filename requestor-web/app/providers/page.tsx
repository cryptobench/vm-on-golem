"use client";

import React from "react";
import { RiFilter3Line } from "@remixicon/react";
import { fetchProviders, computeEstimate, type ProviderAd } from "../../lib/api";
import { useAds } from "../../context/AdsContext";
import { useSettings } from "../../hooks/useSettings";
import { Spinner } from "../../components/ui/Spinner";
import { TableSkeleton } from "../../components/ui/Skeleton";
import { RentDialog } from "../../components/providers/RentDialog";
import {
  ProviderFiltersPanel,
  type ProviderFilters,
} from "../../components/providers/ProviderFiltersPanel";
import { ProvidersTable } from "../../components/providers/ProvidersTable";
import {
  estimateSpec,
  providerMatchesSearch,
  providerPlatform,
} from "../../components/providers/providerDisplay";

const PAGE_SIZE = 10;
const EMPTY_FILTERS: ProviderFilters = {
  search: "",
  country: "",
  platform: "",
};

function providerCountLabel(count: number) {
  return `${count} provider${count === 1 ? "" : "s"}`;
}

function parseNumber(value: string | null) {
  if (value == null || value === "") return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function readFiltersFromUrl(): ProviderFilters {
  if (typeof window === "undefined") return EMPTY_FILTERS;
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

export default function ProvidersPage() {
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
  const pageCount = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const visibleRows = rows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

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
        maxUsd: pending.max_usd_per_month != null ? Number(pending.max_usd_per_month) : filters.maxUsd,
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
    const pageMax = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
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
    setFilters(EMPTY_FILTERS);
    loadProviders(EMPTY_FILTERS);
  };

  return (
    <div
      className={`providers-page grid ${filtersMounted ? "providers-page--filters-mounted" : ""} ${
        filtersOpen ? "providers-page--filters-open" : ""
      }`}
    >
      <div className="min-w-0 space-y-5">
        <div className="flex flex-col gap-4 border-b border-border pb-6 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-text-primary">Providers</h1>
            <p className="mt-1 text-sm text-text-secondary">Browse available providers on the Golem Network.</p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <button className="btn btn-secondary h-11 px-5" onClick={openFilters} type="button">
              <RiFilter3Line className="h-5 w-5" aria-hidden />
              Filter
            </button>
          </div>
        </div>

        <div className="flex flex-col gap-4 border-b border-border pb-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="text-lg font-semibold text-text-primary">
            {providerCountLabel(rows.length)} <span className="text-sm font-normal text-text-secondary">available</span>
          </div>
          <div className="flex flex-wrap items-center gap-3 text-sm text-text-secondary">
            <span>Prices in USD</span>
            <button
              className={`relative h-6 w-11 rounded-full transition ${showTokenPrices ? "bg-primary" : "bg-border-strong"}`}
              onClick={() => setDisplayCurrency(showTokenPrices ? "fiat" : "token")}
              type="button"
              aria-label="Toggle GLM prices"
            >
              <span className={`absolute top-1 h-4 w-4 rounded-full bg-white transition ${showTokenPrices ? "left-6" : "left-1"}`} />
            </button>
            <span>Show price in GLM</span>
          </div>
        </div>

        {error && <div className="rounded-md border border-danger bg-danger-soft p-3 text-sm text-danger">{error}</div>}

        {loading ? (
          <TableSkeleton rows={PAGE_SIZE} cols={7} />
        ) : (
          <>
            <ProvidersTable
              providers={visibleRows}
              spec={spec}
              showTokenPrices={showTokenPrices}
              onSelect={(provider) => setSelectedProvider(provider)}
            />
            {!visibleRows.length && (
              <div className="rounded-lg border border-border bg-surface p-10 text-center text-sm text-text-secondary">
                No providers match these filters.
              </div>
            )}
          </>
        )}

        <div className="grid gap-4 pt-2 text-sm text-text-secondary sm:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] sm:items-center">
          <span className="sm:justify-self-start">
            Showing {rows.length ? (page - 1) * PAGE_SIZE + 1 : 0} to {Math.min(page * PAGE_SIZE, rows.length)} of {providerCountLabel(rows.length)}
          </span>
          <div className="flex items-center justify-center gap-2 sm:justify-self-center">
            <button className="btn btn-secondary h-9 w-9 px-0" onClick={() => setPage((value) => Math.max(1, value - 1))} disabled={page === 1} type="button">‹</button>
            {Array.from({ length: Math.min(3, pageCount) }).map((_, index) => {
              const pageNumber = index + 1;
              return (
                <button
                  className={page === pageNumber ? "btn btn-primary h-9 w-9 px-0" : "btn btn-secondary h-9 w-9 px-0"}
                  key={pageNumber}
                  onClick={() => setPage(pageNumber)}
                  type="button"
                >
                  {pageNumber}
                </button>
              );
            })}
            {pageCount > 4 && <span className="px-2">...</span>}
            {pageCount > 3 && (
              <button className={page === pageCount ? "btn btn-primary h-9 w-9 px-0" : "btn btn-secondary h-9 w-9 px-0"} onClick={() => setPage(pageCount)} type="button">
                {pageCount}
              </button>
            )}
            <button className="btn btn-secondary h-9 w-9 px-0" onClick={() => setPage((value) => Math.min(pageCount, value + 1))} disabled={page === pageCount} type="button">›</button>
          </div>
        </div>
      </div>

      {filtersMounted && (
        <ProviderFiltersPanel
          filters={filters}
          open={filtersOpen}
          countries={countries}
          loadingCountries={loadingCountries}
          resultLabel={providerCountLabel(rows.length)}
          showTokenPrices={showTokenPrices}
          onChange={setFilters}
          onApply={() => loadProviders(filters)}
          onReset={resetFilters}
          onClose={closeFilters}
          onToggleCurrency={() => setDisplayCurrency(showTokenPrices ? "fiat" : "token")}
        />
      )}

      {selectedProvider && (
        <RentDialog
          provider={selectedProvider}
          defaultSpec={spec}
          onClose={() => setSelectedProvider(null)}
          adsMode={ads}
        />
      )}

      {loading && (
        <div className="fixed bottom-4 right-4 hidden items-center gap-2 rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-secondary shadow-soft lg:flex">
          <Spinner className="h-4 w-4" />
          Updating providers
        </div>
      )}
    </div>
  );
}
