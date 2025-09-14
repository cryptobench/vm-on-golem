"use client";
import React from "react";
import { RiCpuLine, RiHardDrive2Line, RiStackLine } from "@remixicon/react";
import { countryFlagEmoji } from "../../lib/intl";

type Pricing = {
  usd_per_core_month?: number | null;
  usd_per_gb_ram_month?: number | null;
  usd_per_gb_storage_month?: number | null;
  glm_per_core_month?: number | null;
  glm_per_gb_ram_month?: number | null;
  glm_per_gb_storage_month?: number | null;
} | null;

// Use shared intl helper for flags

export function ProviderRow({
  provider,
  estimate,
  displayCurrency,
  selected,
  onToggle,
}: {
  provider: {
    provider_id: string;
    provider_name?: string | null;
    ip_address?: string | null;
    country?: string | null;
    platform?: string | null;
    resources: { cpu: number; memory: number; storage: number };
    pricing?: Pricing;
  };
  estimate: null | {
    usd_per_month?: number;
    usd_per_hour?: number;
    glm_per_month?: number;
  };
  displayCurrency: 'fiat' | 'token';
  selected: boolean;
  onToggle: () => void;
}) {
  const name = provider.provider_name?.trim() || provider.provider_id.slice(0, 8);
  const flag = countryFlagEmoji(provider.country || '');

  // Price summary lines
  let priceHourLine: string | null = null;
  let priceMonthLine: string | null = null;
  if (estimate) {
    if (displayCurrency === 'token' && estimate.glm_per_month != null) {
      priceHourLine = `~${(estimate.glm_per_month / 730).toFixed(8)} GLM/hr`;
      priceMonthLine = `≈ ${Number(estimate.glm_per_month).toFixed(6)} GLM/mo`;
    } else if (estimate.usd_per_hour != null && estimate.usd_per_month != null) {
      priceHourLine = `~$${estimate.usd_per_hour}/hr`;
      priceMonthLine = `≈ $${Number(estimate.usd_per_month).toFixed(2)}/mo`;
    }
  }

  // Per-unit pricing (not shown on the right; optional to use elsewhere)
  // const pr = (provider.pricing || {}) as any;
  // const showToken = displayCurrency === 'token';

  return (
    <div
      className={
        "box-border flex flex-col border bg-white px-6 py-6 cursor-pointer select-none " +
        (selected ? "border-[#181E9F]" : "border-gray-200 hover:border-gray-300")
      }
      onClick={onToggle}
      role="button"
      aria-pressed={selected}
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); onToggle(); } }}
    >
      <div className="flex flex-row items-center gap-4">
        {/* Main info */}
        <div className="flex w-full min-w-0 flex-[2] flex-row items-start gap-4">
          <div className="flex min-w-0 flex-1 flex-col justify-center gap-2">
            <div className="flex items-center gap-2 min-w-0">
              {flag && <span className="text-base leading-none" title={provider.country || ''}>{flag}</span>}
              <div className="truncate text-base font-medium text-gray-900" title={provider.provider_name || provider.provider_id}>{name}</div>
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-600 ring-2 ring-emerald-200" aria-hidden />
            </div>
            <div className="flex items-center gap-3 text-xs text-gray-500">
              <span className="font-mono break-all" title={provider.provider_id}>{provider.provider_id}</span>
              {provider.platform && <span className="rounded border px-1.5 py-0.5 text-[11px] text-gray-700">{provider.platform}</span>}
              {provider.ip_address && <span className="text-gray-600">{provider.ip_address}</span>}
            </div>
            {/* Capacity (totals only) */}
            <div className="mt-2 flex flex-row flex-wrap items-center gap-4 text-[12px] text-gray-700">
              <span className="rounded bg-gray-100 px-1.5 py-0.5 text-[11px] text-gray-600">Capacity (total)</span>
              <span className="inline-flex items-center gap-1.5" title="Total cores available">
                <RiCpuLine className="h-4 w-4 text-gray-500" />
                Cores: <span className="font-mono">{provider.resources.cpu}</span>
              </span>
              <span className="inline-flex items-center gap-1.5" title="Total memory available">
                <RiStackLine className="h-4 w-4 text-gray-500" />
                Memory: <span className="font-mono">{provider.resources.memory} GB</span>
              </span>
              <span className="inline-flex items-center gap-1.5" title="Total storage available">
                <RiHardDrive2Line className="h-4 w-4 text-gray-500" />
                Disk: <span className="font-mono">{provider.resources.storage} GB</span>
              </span>
            </div>
            {/* Hourly price under specs */}
            {priceHourLine && (
              <div className="mt-1 text-[12px] text-gray-700">Hourly: <span className="font-medium">{priceHourLine}</span></div>
            )}
          </div>
        </div>

        {/* Price area (right): monthly only */}
        <div className="flex min-w-[220px] flex-[1] items-start justify-start">
          {priceMonthLine && (
            <div className="text-base font-semibold text-gray-900">{priceMonthLine}</div>
          )}
        </div>

        {/* Right side: selection checkbox */}
        <div className="flex items-center justify-end pl-2">
          <input
            type="checkbox"
            className="h-4 w-4 border-gray-400"
            checked={selected}
            onChange={(e) => { e.stopPropagation(); onToggle(); }}
            onClick={(e) => e.stopPropagation()}
            aria-label={selected ? 'Deselect provider' : 'Select provider'}
          />
        </div>
      </div>
    </div>
  );
}
