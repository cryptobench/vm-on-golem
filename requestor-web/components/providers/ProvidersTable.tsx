"use client";

import React from "react";
import { RiArrowRightSLine, RiUbuntuLine, RiWindowsLine } from "@remixicon/react";
import { computeEstimate, type ProviderAd } from "../../lib/api";
import { countryFlagEmoji } from "../../lib/intl";
import { providerLocation, providerPlatform, shortProviderId, type ProviderSpec } from "./providerDisplay";

function formatUsd(value?: number) {
  return value == null ? "-" : `$${value.toFixed(value < 1 ? 4 : 2)}`;
}

function formatGlm(value?: number) {
  return value == null ? "-" : `${value.toFixed(3)} GLM`;
}

export function ProvidersTable({
  providers,
  spec,
  showTokenPrices,
  onSelect,
}: {
  providers: ProviderAd[];
  spec: Required<ProviderSpec>;
  showTokenPrices: boolean;
  onSelect: (provider: ProviderAd) => void;
}) {
  return (
    <div className="providers-table-shell overflow-x-auto">
      <table className="w-full min-w-max border-collapse text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs font-medium text-text-secondary">
            <th className="py-4 pr-4">Provider ID</th>
            <th className="px-4 py-4">Location</th>
            <th className="px-4 py-4">Platform</th>
            <th className="px-4 py-4">Total vCPU</th>
            <th className="px-4 py-4">Total RAM</th>
            <th className="px-4 py-4">Total Storage</th>
            <th className="px-4 py-4">Est. Monthly<br />(from)</th>
            <th className="px-4 py-4">Est. Hourly<br />(from)</th>
            {showTokenPrices && <th className="px-4 py-4">Est. Hourly<br />(GLM)</th>}
            <th className="py-4 pl-4" aria-label="Open provider" />
          </tr>
        </thead>
        <tbody>
          {providers.map((provider) => {
            const location = providerLocation(provider);
            const locationFlag = countryFlagEmoji(location.code);
            const platform = providerPlatform(provider);
            const PlatformIcon = platform === "Windows" ? RiWindowsLine : RiUbuntuLine;
            const estimate = computeEstimate(provider, spec.cpu, spec.memory, spec.storage);
            return (
              <tr
                className="providers-table-row cursor-pointer border-b border-border text-text-primary hover:bg-surface-muted"
                key={provider.provider_id}
                onClick={() => onSelect(provider)}
                tabIndex={0}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onSelect(provider);
                  }
                }}
              >
                <td className="py-4 pr-4 font-mono">{shortProviderId(provider.provider_id)}</td>
                <td className="px-4 py-4">
                  <span className="grid grid-cols-[auto_1fr] items-start gap-x-2">
                    {locationFlag && <span className="text-base leading-none">{locationFlag}</span>}
                    <span className="col-start-2 block font-medium leading-none">{location.code || "-"}</span>
                    <span className="col-start-2 mt-1 block text-xs text-text-secondary">
                      {location.name}
                    </span>
                  </span>
                </td>
                <td className="px-4 py-4">
                  <span className="inline-flex items-center gap-2">
                    <PlatformIcon className="h-4 w-4 text-primary" aria-hidden />
                    {platform}
                  </span>
                </td>
                <td className="px-4 py-4">{provider.resources.cpu} vCPU</td>
                <td className="px-4 py-4">{provider.resources.memory} GB</td>
                <td className="px-4 py-4">{provider.resources.storage >= 1024 ? `${(provider.resources.storage / 1024).toFixed(1)} TB` : `${provider.resources.storage} GB`}</td>
                <td className="px-4 py-4">{formatUsd(estimate.usd_per_month)}</td>
                <td className="px-4 py-4">{formatUsd(estimate.usd_per_hour)}</td>
                {showTokenPrices && <td className="px-4 py-4 font-medium text-primary">{formatGlm(estimate.glm_per_month == null ? undefined : estimate.glm_per_month / 730)}</td>}
                <td className="py-4 pl-4 text-right">
                  <RiArrowRightSLine className="h-5 w-5 text-text-secondary" aria-hidden />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
