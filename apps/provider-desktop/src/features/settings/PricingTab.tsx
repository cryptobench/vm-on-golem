import { Button, Callout, Card, CardBody, IconTile, SectionHeader } from "@golem/ui";
import { RiSaveLine } from "@remixicon/react";
import { formatGlm } from "../../lib/format";
import { usdToGlm } from "../../lib/prices";
import type { ProviderSettings, UpdateProviderPricing } from "../../lib/types";
import { PRICING_FIELDS, type PricingField } from "./settingsConstants";

export function PricingTab({
  settings,
  draft,
  glmUsd,
  saving,
  onDraftChange,
  onSave,
}: {
  settings: ProviderSettings;
  draft: UpdateProviderPricing;
  glmUsd: number | null;
  saving: boolean;
  onDraftChange: (pricing: UpdateProviderPricing) => void;
  onSave: () => void;
}) {
  const changed =
    draft.usd_per_core_month !== settings.pricing.usd_per_core_month ||
    draft.usd_per_gb_ram_month !== settings.pricing.usd_per_gb_ram_month ||
    draft.usd_per_gb_storage_month !== settings.pricing.usd_per_gb_storage_month;

  return (
    <div className="space-y-5">
      <Card>
        <CardBody className="space-y-5">
          <SectionHeader
            title="Configure Pricing"
            description="Set your rental price for each resource type."
          />
          <div className="space-y-3">
            {PRICING_FIELDS.map((field) => {
              const usd = draft[field.key];
              const glm = settings.pricing[field.glmKey] > 0
                ? settings.pricing[field.glmKey]
                : usdToGlm(usd, glmUsd);
              return (
                <PricingControl
                  key={field.key}
                  field={field}
                  value={usd}
                  glmValue={glm}
                  onChange={(value) =>
                    onDraftChange({
                      ...draft,
                      [field.key]: Math.max(0, Number.isFinite(value) ? value : 0),
                    })
                  }
                />
              );
            })}
          </div>
        </CardBody>
      </Card>

      <div className="flex flex-col gap-4 md:flex-row md:items-center">
        <Button
          className="w-full md:w-auto"
          busy={saving}
          disabled={!changed || saving}
          onClick={onSave}
        >
          <RiSaveLine className="h-4 w-4" aria-hidden />
          Save Pricing
        </Button>
        <Callout className="flex-1">
          Price updates apply to future rentals. Existing active rentals keep
          their current terms.
        </Callout>
      </div>
    </div>
  );
}

function PricingControl({
  field,
  value,
  glmValue,
  onChange,
}: {
  field: PricingField;
  value: number;
  glmValue: number | null;
  onChange: (value: number) => void;
}) {
  return (
    <div className="grid gap-4 rounded-lg border border-border px-4 py-4 lg:grid-cols-[1fr_18rem] lg:items-center">
      <div className="flex items-center gap-3">
        <IconTile tone="neutral" className="h-11 w-11">
          {field.icon}
        </IconTile>
        <div>
          <div className="font-semibold text-text-primary">{field.label}</div>
          <div className="text-sm text-text-secondary">{field.description}</div>
        </div>
      </div>
      <div>
        <label className="flex h-10 overflow-hidden rounded-md border border-border bg-surface">
          <span className="grid place-items-center border-r border-border px-3 text-sm font-semibold text-text-secondary">
            $
          </span>
          <input
            type="number"
            min={0}
            step={0.01}
            value={value}
            onChange={(event) => onChange(Number(event.target.value))}
            className="min-w-0 flex-1 border-0 bg-transparent px-3 text-sm font-medium text-text-primary focus:ring-0"
            aria-label={field.label}
          />
          <span className="grid place-items-center border-l border-border px-3 text-sm font-medium text-text-secondary">
            USD
          </span>
        </label>
        <div className="mt-2 text-sm text-text-secondary">
          ≈ {formatGlm(glmValue)} {field.unit}
        </div>
      </div>
    </div>
  );
}
