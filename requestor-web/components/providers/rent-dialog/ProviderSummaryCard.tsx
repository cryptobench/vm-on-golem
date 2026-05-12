"use client";

import React from "react";
import { RiExternalLinkLine, RiServerLine } from "@remixicon/react";
import type { ProviderAd } from "../../../lib/api";
import { countryFlagEmoji } from "../../../lib/intl";
import { providerLocation, shortProviderId } from "../providerDisplay";

export function ProviderSummaryCard({ provider }: { provider: ProviderAd }) {
  const location = providerLocation(provider);

  return (
    <section className="rounded-lg border border-border bg-surface p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="text-xs font-medium text-text-secondary">Selected provider</div>
        <span className="rounded-md bg-success-soft px-2 py-1 text-xs font-medium text-success">
          Online
        </span>
      </div>
      <div className="mt-4 flex items-center gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md border border-border bg-surface-muted text-text-secondary">
          <RiServerLine className="h-5 w-5" aria-hidden />
        </div>
        <div className="min-w-0">
          <div className="text-xs text-text-secondary">Provider ID</div>
          <div className="truncate font-mono text-sm font-semibold text-text-primary" title={provider.provider_id}>
            {shortProviderId(provider.provider_id)}
          </div>
        </div>
      </div>
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2 text-sm text-text-primary">
          <span aria-hidden>{countryFlagEmoji(location.code)}</span>
          <span className="truncate">
            {location.code || "Unknown"} {location.name ? `- ${location.name}` : ""}
          </span>
        </div>
        <a
          className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:text-primary-hover"
          href={`/providers?q=${encodeURIComponent(provider.provider_id)}`}
        >
          View provider details
          <RiExternalLinkLine className="h-4 w-4" aria-hidden />
        </a>
      </div>
    </section>
  );
}
