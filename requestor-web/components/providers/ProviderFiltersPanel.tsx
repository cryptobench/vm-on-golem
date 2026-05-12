"use client";

import React from "react";
import {
  RiArrowDownSLine,
  RiCloseLine,
  RiInformationLine,
  RiSearchLine,
} from "@remixicon/react";
import { countryFlagEmoji, countryFullName } from "../../lib/intl";
import { Spinner } from "../ui/Spinner";

export type ProviderFilters = {
  search: string;
  country: string;
  platform: string;
  cpu?: number;
  memory?: number;
  storage?: number;
  maxUsd?: number;
};

function NumberStepper({
  label,
  value,
  onChange,
}: {
  label: string;
  value?: number;
  onChange: (value?: number) => void;
}) {
  const update = (next?: number) => onChange(next && next > 0 ? next : undefined);
  return (
    <label className="block">
      <span className="mb-2 block text-sm text-text-secondary">{label}</span>
      <span className="grid h-10 grid-cols-[1fr_40px_40px] overflow-hidden rounded-md border border-border bg-surface">
        <input
          className="min-w-0 border-0 bg-transparent px-3 text-sm outline-none focus:ring-0"
          value={value ?? ""}
          onChange={(event) => update(event.target.value ? Number(event.target.value) : undefined)}
          placeholder="Any"
          type="number"
          min={1}
        />
        <button className="border-l border-border text-lg text-text-secondary hover:bg-surface-muted" onClick={() => update((value || 0) - 1)} type="button">−</button>
        <button className="border-l border-border text-lg text-text-secondary hover:bg-surface-muted" onClick={() => update((value || 0) + 1)} type="button">+</button>
      </span>
    </label>
  );
}

export function ProviderFiltersPanel({
  filters,
  open,
  countries,
  loadingCountries,
  resultLabel,
  showTokenPrices,
  onChange,
  onApply,
  onReset,
  onClose,
  onToggleCurrency,
}: {
  filters: ProviderFilters;
  open: boolean;
  countries: string[];
  loadingCountries: boolean;
  resultLabel: string;
  showTokenPrices: boolean;
  onChange: (next: ProviderFilters) => void;
  onApply: () => void;
  onReset: () => void;
  onClose: () => void;
  onToggleCurrency: () => void;
}) {
  const patch = (next: Partial<ProviderFilters>) => onChange({ ...filters, ...next });

  return (
    <aside
      className={`providers-filter-panel rounded-lg border border-border bg-surface lg:rounded-none lg:border-y-0 lg:border-r-0 ${
        open ? "providers-filter-panel--open" : "providers-filter-panel--closed"
      }`}
    >
      <div className="flex items-center justify-between px-5 py-5">
        <h2 className="text-xl font-semibold tracking-tight text-text-primary">Filters</h2>
        <div className="flex items-center gap-4">
          <button className="text-sm font-medium text-primary" onClick={onReset} type="button">Reset all</button>
          <button className="text-text-secondary hover:text-text-primary" onClick={onClose} type="button" aria-label="Close filters">
            <RiCloseLine className="h-5 w-5" aria-hidden />
          </button>
        </div>
      </div>

      <div className="space-y-6 px-5 pb-5">
        <label className="block">
          <span className="mb-2 block text-sm font-medium text-text-primary">Search</span>
          <span className="flex h-10 items-center gap-2 rounded-md border border-border bg-surface px-3">
            <RiSearchLine className="h-4 w-4 text-text-muted" aria-hidden />
            <input
              className="min-w-0 flex-1 border-0 bg-transparent p-0 text-sm outline-none placeholder:text-text-muted focus:ring-0"
              placeholder="Search by provider ID, location or IP..."
              value={filters.search}
              onChange={(event) => patch({ search: event.target.value })}
            />
          </span>
        </label>

        <label className="block">
          <span className="mb-2 flex items-center gap-1 text-sm font-medium text-text-primary">
            Location <RiInformationLine className="h-4 w-4 text-text-muted" aria-hidden />
          </span>
          <span className="relative block">
            <select className="input appearance-none pr-9" value={filters.country} onChange={(event) => patch({ country: event.target.value })} disabled={loadingCountries}>
              <option value="">All countries</option>
              {countries.map((code) => (
                <option key={code} value={code}>{countryFlagEmoji(code)} {countryFullName(code)}</option>
              ))}
            </select>
            {loadingCountries ? <Spinner className="absolute right-3 top-2.5 h-4 w-4" /> : <RiArrowDownSLine className="pointer-events-none absolute right-3 top-2.5 h-5 w-5 text-text-secondary" aria-hidden />}
          </span>
        </label>

        <label className="block">
          <span className="mb-2 block text-sm font-medium text-text-primary">Platform</span>
          <span className="relative block">
            <select className="input appearance-none pr-9" value={filters.platform} onChange={(event) => patch({ platform: event.target.value })}>
              <option value="">All platforms</option>
              <option value="linux">Linux</option>
              <option value="windows">Windows</option>
            </select>
            <RiArrowDownSLine className="pointer-events-none absolute right-3 top-2.5 h-5 w-5 text-text-secondary" aria-hidden />
          </span>
        </label>
      </div>

      <div className="space-y-4 border-t border-border px-5 py-5">
        <div className="flex items-center gap-1 text-sm font-medium text-text-primary">
          Capacity <span className="font-normal text-text-secondary">(minimum)</span>
          <RiInformationLine className="h-4 w-4 text-text-muted" aria-hidden />
        </div>
        <NumberStepper label="vCPU" value={filters.cpu} onChange={(cpu) => patch({ cpu })} />
        <NumberStepper label="RAM (GB)" value={filters.memory} onChange={(memory) => patch({ memory })} />
        <NumberStepper label="Storage (GB)" value={filters.storage} onChange={(storage) => patch({ storage })} />
      </div>

      <div className="space-y-5 border-t border-border px-5 py-5">
        <div className="flex items-center gap-1 text-sm font-medium text-text-primary">
          Price <RiInformationLine className="h-4 w-4 text-text-muted" aria-hidden />
        </div>
        <label className="block">
          <span className="mb-2 block text-sm text-text-secondary">Max monthly price (USD)</span>
          <input
            className="input"
            min={0}
            onChange={(event) => patch({ maxUsd: event.target.value ? Number(event.target.value) : undefined })}
            placeholder="Any price"
            step="0.01"
            type="number"
            value={filters.maxUsd ?? ""}
          />
        </label>
        <button className="inline-flex items-center gap-2 text-sm text-text-secondary transition-colors hover:text-text-primary" onClick={onToggleCurrency} type="button">
          <span className={`relative h-6 w-11 rounded-full transition ${showTokenPrices ? "bg-primary" : "bg-border-strong"}`}>
            <span className={`absolute top-1 h-4 w-4 rounded-full bg-white transition ${showTokenPrices ? "left-6" : "left-1"}`} />
          </span>
          Show price in GLM
          <RiInformationLine className="h-4 w-4 text-text-muted" aria-hidden />
        </button>
        <button className="btn btn-primary h-11 w-full" onClick={onApply} type="button">Apply filters</button>
        <div className="text-center text-sm font-medium text-primary">{resultLabel}</div>
      </div>
    </aside>
  );
}
