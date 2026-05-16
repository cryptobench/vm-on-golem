import { Callout, IconTile } from "@golem/ui";
import { RiLineChartLine } from "@remixicon/react";
import { formatCurrency, formatGlm } from "../../lib/format";
import type { UpdateProviderPricing, VMResources } from "../../lib/types";
import { EarningsLine } from "./SettingsShared";

export function EstimatePanel({
  estimate,
  pricing,
  estimateUsd,
  estimateGlm,
}: {
  estimate: VMResources;
  pricing: UpdateProviderPricing;
  estimateUsd: number;
  estimateGlm: number | null;
}) {
  return (
    <div className="rounded-lg border border-primary-soft bg-surface px-5 py-5">
      <div className="flex items-center gap-3">
        <IconTile tone="primary" className="h-11 w-11">
          <RiLineChartLine className="h-5 w-5" />
        </IconTile>
        <h3 className="font-semibold text-text-primary">Monthly Earnings</h3>
      </div>
      <div className="mt-6 space-y-4">
        <EarningsLine
          label="CPU"
          detail={`${estimate.cpu} × ${formatCurrency(pricing.usd_per_core_month)}`}
          value={formatCurrency(estimate.cpu * pricing.usd_per_core_month)}
        />
        <EarningsLine
          label="Memory"
          detail={`${estimate.memory} × ${formatCurrency(pricing.usd_per_gb_ram_month)}`}
          value={formatCurrency(estimate.memory * pricing.usd_per_gb_ram_month)}
        />
        <EarningsLine
          label="Storage"
          detail={`${estimate.storage} × ${formatCurrency(pricing.usd_per_gb_storage_month)}`}
          value={formatCurrency(estimate.storage * pricing.usd_per_gb_storage_month)}
        />
      </div>
      <div className="mt-6 border-t border-border pt-5">
        <div className="flex items-baseline justify-between gap-4">
          <span className="font-semibold text-text-primary">Total (USD)</span>
          <span className="text-2xl font-semibold text-primary tabular-nums">
            {formatCurrency(estimateUsd)}
          </span>
        </div>
        <div className="mt-4 flex justify-between gap-4 text-sm text-text-secondary">
          <span>Approx. total (GLM)</span>
          <span>{formatGlm(estimateGlm)}</span>
        </div>
      </div>
      <Callout className="mt-6">
        Assumes resources are rented for the full month.
      </Callout>
    </div>
  );
}
