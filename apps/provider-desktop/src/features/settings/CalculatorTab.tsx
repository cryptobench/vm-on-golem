import React from "react";
import { Card, CardBody, IconTile, SectionHeader } from "@golem/ui";
import { RiMoneyDollarCircleLine } from "@remixicon/react";
import { formatCurrency, formatGlm } from "../../lib/format";
import { usdToGlm } from "../../lib/prices";
import type { ProviderSettings, UpdateProviderPricing, VMResources } from "../../lib/types";
import { EstimatePanel } from "./CalculatorEstimatePanel";
import { ResourceControl } from "./ResourceControl";
import { RESOURCE_FIELDS, type ResourceKey } from "./settingsConstants";
import { calculateEarnings, clampWhole } from "./settingsUtils";

export function CalculatorTab({
  settings,
  pricing,
  glmUsd,
}: {
  settings: ProviderSettings;
  pricing: UpdateProviderPricing;
  glmUsd: number | null;
}) {
  const [estimate, setEstimate] = React.useState<VMResources>(() => ({
    cpu: Math.max(1, Math.min(8, settings.offered_resources.cpu)),
    memory: Math.max(1, Math.min(32, settings.offered_resources.memory)),
    storage: Math.max(1, Math.min(100, settings.offered_resources.storage)),
  }));

  React.useEffect(() => {
    setEstimate((current) => ({
      cpu: clampWhole(current.cpu, 1, Math.max(1, settings.offered_resources.cpu)),
      memory: clampWhole(
        current.memory,
        1,
        Math.max(1, settings.offered_resources.memory),
      ),
      storage: clampWhole(
        current.storage,
        1,
        Math.max(1, settings.offered_resources.storage),
      ),
    }));
  }, [settings.offered_resources]);

  const estimateUsd = calculateEarnings(estimate, pricing);
  const estimateGlm = usdToGlm(estimateUsd, glmUsd);
  const fullUsd = calculateEarnings(settings.offered_resources, pricing);
  const fullGlm = usdToGlm(fullUsd, glmUsd);

  const setValue = (key: ResourceKey, value: number) => {
    setEstimate({
      ...estimate,
      [key]: clampWhole(value, 1, Math.max(1, settings.offered_resources[key])),
    });
  };

  return (
    <div className="space-y-5">
      <Card>
        <CardBody>
          <div className="grid gap-6 xl:grid-cols-[1fr_26rem]">
            <div className="space-y-5">
              <SectionHeader
                title="Earnings Calculator"
                description="Scale the amount of rented resources with your current pricing to calculate your possible earnings."
              />
              <div className="space-y-4">
                {RESOURCE_FIELDS.map((field) => (
                  <ResourceControl
                    key={field.key}
                    field={{
                      ...field,
                      label: `${field.label.replace(" (RAM)", "")} Rented`,
                      description: `Select ${field.description.toLowerCase()}`,
                    }}
                    value={estimate[field.key]}
                    min={1}
                    max={Math.max(1, settings.offered_resources[field.key])}
                    allocated={settings.allocated_resources[field.key]}
                    showValueInput={false}
                    showLimits={false}
                    onChange={(value) => setValue(field.key, value)}
                  />
                ))}
              </div>
            </div>
            <EstimatePanel
              estimate={estimate}
              pricing={pricing}
              estimateUsd={estimateUsd}
              estimateGlm={estimateGlm}
            />
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardBody className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-4">
            <IconTile tone="primary" className="h-12 w-12">
              <RiMoneyDollarCircleLine className="h-6 w-6" />
            </IconTile>
            <div>
              <div className="font-semibold text-text-primary">
                If all currently offered resources were rented out, monthly
                earnings would be higher.
              </div>
              <div className="mt-1 text-sm text-text-secondary">
                Based on your current available resources and pricing.
              </div>
            </div>
          </div>
          <div className="text-left md:text-right">
            <div className="text-2xl font-semibold text-primary tabular-nums">
              {formatCurrency(fullUsd)}
            </div>
            <div className="mt-1 text-sm text-text-secondary">
              ≈ {formatGlm(fullGlm)}
            </div>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
