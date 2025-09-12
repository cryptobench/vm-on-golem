"use client";
import React from "react";
import { RiCpuLine, RiDatabase2Line, RiHardDrive2Line, RiStackLine } from "@remixicon/react";

type Pricing = {
  usd_per_core_month?: number | null;
  usd_per_gb_ram_month?: number | null;
  usd_per_gb_storage_month?: number | null;
  glm_per_core_month?: number | null;
  glm_per_gb_ram_month?: number | null;
  glm_per_gb_storage_month?: number | null;
} | null;

export function codeToFlagEmoji(code?: string | null) {
  if (!code) return "";
  const cc = code.trim().toUpperCase();
  if (!/^[A-Z]{2}$/.test(cc)) return cc;
  const A = 0x1f1e6;
  const base = "A".charCodeAt(0);
  const first = A + (cc.charCodeAt(0) - base);
  const second = A + (cc.charCodeAt(1) - base);
  return String.fromCodePoint(first) + String.fromCodePoint(second);
}

export function ProviderRow({
  provider,
  estimate,
  displayCurrency,
  rightAction,
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
  rightAction?: React.ReactNode;
}) {
  const name = provider.provider_name?.trim() || provider.provider_id.slice(0, 8);
  const flag = codeToFlagEmoji(provider.country);

  // Price summary line (hourly)
  let priceLine: string | null = null;
  if (estimate) {
    if (displayCurrency === 'token' && estimate.glm_per_month != null) {
      priceLine = `~${(estimate.glm_per_month / 730).toFixed(8)} GLM/hr`;
    } else if (estimate.usd_per_hour != null) {
      priceLine = `~$${estimate.usd_per_hour}/hr`;
    }
  }

  // Per-unit pricing badges (optional)
  const pr = (provider.pricing || {}) as any;
  const showToken = displayCurrency === 'token';
  const coreM = showToken ? pr.glm_per_core_month : pr.usd_per_core_month;
  const ramM = showToken ? pr.glm_per_gb_ram_month : pr.usd_per_gb_ram_month;
  const stoM = showToken ? pr.glm_per_gb_storage_month : pr.usd_per_gb_storage_month;

  return (
    <div className="box-border flex flex-col rounded-lg border border-gray-200 bg-white px-6 py-6">
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
            {/* Resource badges */}
            <div className="mt-2 flex flex-row flex-wrap items-center gap-4 text-[12px] text-gray-700">
              <span className="inline-flex items-center gap-1.5"><RiCpuLine className="h-4 w-4 text-gray-500" /> Cores: <span className="font-mono">{provider.resources.cpu}</span></span>
              <span className="inline-flex items-center gap-1.5"><RiStackLine className="h-4 w-4 text-gray-500" /> Memory: <span className="font-mono">{provider.resources.memory} GB</span></span>
              <span className="inline-flex items-center gap-1.5"><RiHardDrive2Line className="h-4 w-4 text-gray-500" /> Disk: <span className="font-mono">{provider.resources.storage} GB</span></span>
            </div>
          </div>
        </div>

        {/* Price area */}
        <div className="flex min-w-[220px] flex-[1] flex-col items-start gap-2">
          {priceLine && (
            <div className="text-sm text-gray-900">{priceLine}</div>
          )}
          {(coreM != null || ramM != null || stoM != null) && (
            <div className="text-[11px] text-gray-600">
              {coreM != null && (<div>Core: <span className="font-mono">{Number(coreM).toFixed(showToken ? 6 : 4)}</span>{showToken ? ' GLM/mo' : '/mo'}</div>)}
              {ramM != null && (<div>RAM: <span className="font-mono">{Number(ramM).toFixed(showToken ? 6 : 4)}</span>{showToken ? ' GLM/GB·mo' : '/GB·mo'}</div>)}
              {stoM != null && (<div>Storage: <span className="font-mono">{Number(stoM).toFixed(showToken ? 6 : 4)}</span>{showToken ? ' GLM/GB·mo' : '/GB·mo'}</div>)}
            </div>
          )}
        </div>

        {/* Right action (Rent button centered) */}
        <div className="flex items-center justify-end">{rightAction}</div>
      </div>
    </div>
  );
}
