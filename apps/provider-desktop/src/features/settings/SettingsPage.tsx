import React from "react";
import { Callout, Card, CardBody, PageHeader, Tabs } from "@golem/ui";
import { providerApi } from "../../lib/providerApi";
import { useGlmUsdPrice } from "../../lib/prices";
import type {
  ProviderSettings,
  UpdateProviderPricing,
  VMResources,
} from "../../lib/types";
import { CalculatorTab } from "./CalculatorTab";
import { PricingTab } from "./PricingTab";
import { ResourcesTab } from "./ResourcesTab";
import { SettingsSkeleton } from "./SettingsShared";
import { SETTINGS_TABS, type SettingsTab } from "./settingsConstants";
import { messageFromError } from "./settingsUtils";

export function SettingsPage({ onRefresh }: { onRefresh: () => Promise<void> }) {
  const glmUsd = useGlmUsdPrice();
  const [activeTab, setActiveTab] = React.useState<SettingsTab>("resources");
  const [settings, setSettings] = React.useState<ProviderSettings | null>(null);
  const [resourceDraft, setResourceDraft] = React.useState<VMResources | null>(null);
  const [pricingDraft, setPricingDraft] =
    React.useState<UpdateProviderPricing | null>(null);
  const [loadingSettings, setLoadingSettings] = React.useState(true);
  const [saving, setSaving] = React.useState<"resources" | "pricing" | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [notice, setNotice] = React.useState<string | null>(null);

  const applySettings = React.useCallback((next: ProviderSettings) => {
    setSettings(next);
    setResourceDraft(next.offered_resources);
    setPricingDraft({
      usd_per_core_month: next.pricing.usd_per_core_month,
      usd_per_gb_ram_month: next.pricing.usd_per_gb_ram_month,
      usd_per_gb_storage_month: next.pricing.usd_per_gb_storage_month,
    });
  }, []);

  React.useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoadingSettings(true);
      setError(null);
      try {
        const next = await providerApi.providerSettings();
        if (!cancelled) applySettings(next);
      } catch (err) {
        if (!cancelled) setError(messageFromError(err));
      } finally {
        if (!cancelled) setLoadingSettings(false);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [applySettings]);

  const saveResources = async () => {
    if (!resourceDraft) return;
    setSaving("resources");
    setError(null);
    setNotice(null);
    try {
      const next = await providerApi.updateProviderResources(resourceDraft);
      applySettings(next);
      setNotice("Resource settings saved.");
      await onRefresh();
    } catch (err) {
      setError(messageFromError(err));
    } finally {
      setSaving(null);
    }
  };

  const savePricing = async () => {
    if (!pricingDraft) return;
    setSaving("pricing");
    setError(null);
    setNotice(null);
    try {
      const next = await providerApi.updateProviderPricing(pricingDraft);
      applySettings(next);
      setNotice(next.pricing.warning ?? "Pricing saved.");
      await onRefresh();
    } catch (err) {
      setError(messageFromError(err));
    } finally {
      setSaving(null);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Settings"
        description="Configure the resources and pricing for renting out your virtual machines."
      />
      <Tabs tabs={SETTINGS_TABS} active={activeTab} onChange={setActiveTab} />
      {error ? <Callout tone="danger">{error}</Callout> : null}
      {notice ? (
        <Callout tone={notice.includes("Could not") ? "warning" : "info"}>
          {notice}
        </Callout>
      ) : null}
      <SettingsBody
        activeTab={activeTab}
        settings={settings}
        resourceDraft={resourceDraft}
        pricingDraft={pricingDraft}
        loading={loadingSettings}
        saving={saving}
        glmUsd={glmUsd}
        onResourceDraftChange={setResourceDraft}
        onPricingDraftChange={setPricingDraft}
        onSaveResources={() => void saveResources()}
        onSavePricing={() => void savePricing()}
      />
    </div>
  );
}

function SettingsBody({
  activeTab,
  settings,
  resourceDraft,
  pricingDraft,
  loading,
  saving,
  glmUsd,
  onResourceDraftChange,
  onPricingDraftChange,
  onSaveResources,
  onSavePricing,
}: {
  activeTab: SettingsTab;
  settings: ProviderSettings | null;
  resourceDraft: VMResources | null;
  pricingDraft: UpdateProviderPricing | null;
  loading: boolean;
  saving: "resources" | "pricing" | null;
  glmUsd: number | null;
  onResourceDraftChange: (resources: VMResources) => void;
  onPricingDraftChange: (pricing: UpdateProviderPricing) => void;
  onSaveResources: () => void;
  onSavePricing: () => void;
}) {
  if (loading && !settings) return <SettingsSkeleton />;
  if (!settings || !resourceDraft || !pricingDraft) {
    return (
      <Card>
        <CardBody>
          <p className="text-sm text-text-secondary">
            Provider settings are unavailable.
          </p>
        </CardBody>
      </Card>
    );
  }
  if (activeTab === "resources") {
    return (
      <ResourcesTab
        settings={settings}
        draft={resourceDraft}
        saving={saving === "resources"}
        onDraftChange={onResourceDraftChange}
        onSave={onSaveResources}
      />
    );
  }
  if (activeTab === "pricing") {
    return (
      <PricingTab
        settings={settings}
        draft={pricingDraft}
        glmUsd={glmUsd}
        saving={saving === "pricing"}
        onDraftChange={onPricingDraftChange}
        onSave={onSavePricing}
      />
    );
  }
  return (
    <CalculatorTab settings={settings} pricing={pricingDraft} glmUsd={glmUsd} />
  );
}
