import { Button, Card, CardBody, SectionHeader } from "@golem/ui";
import { RiSaveLine } from "@remixicon/react";
import type { ProviderSettings, VMResources } from "../../lib/types";
import { ResourceControl } from "./ResourceControl";
import { RESOURCE_FIELDS, type ResourceKey } from "./settingsConstants";
import { clampWhole, sameResources } from "./settingsUtils";

export function ResourcesTab({
  settings,
  draft,
  saving,
  onDraftChange,
  onSave,
}: {
  settings: ProviderSettings;
  draft: VMResources;
  saving: boolean;
  onDraftChange: (resources: VMResources) => void;
  onSave: () => void;
}) {
  const min = settings.minimum_configurable_resources;
  const max = settings.detected_resources;
  const changed = !sameResources(draft, settings.offered_resources);

  const setValue = (key: ResourceKey, value: number) => {
    onDraftChange({
      ...draft,
      [key]: clampWhole(value, min[key], max[key]),
    });
  };

  return (
    <div className="space-y-5">
      <Card>
        <CardBody className="space-y-5">
          <SectionHeader
            title="Configure Resources"
            description="Set how many resources are available for future rentals."
          />
          <div className="space-y-3">
            {RESOURCE_FIELDS.map((field) => (
              <ResourceControl
                key={field.key}
                field={field}
                value={draft[field.key]}
                min={min[field.key]}
                max={max[field.key]}
                allocated={settings.allocated_resources[field.key]}
                showValueInput={false}
                onChange={(value) => setValue(field.key, value)}
              />
            ))}
          </div>
        </CardBody>
      </Card>

      <div>
        <Button
          className="w-full md:w-auto"
          busy={saving}
          disabled={!changed || saving}
          onClick={onSave}
        >
          <RiSaveLine className="h-4 w-4" aria-hidden />
          Save Resources
        </Button>
      </div>
    </div>
  );
}
