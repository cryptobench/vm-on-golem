import React from "react";
import { providerApi } from "../../lib/providerApi";
import type {
  WebhookConfig,
  WebhookDeliveryAttempt,
  WebhookEventType,
  WebhookTestResponse,
} from "../../lib/types";
import type { DashboardData } from "../../lib/useProviderData";
import { createDefaultWebhook } from "./webhookConstants";
import type {
  DialogStep,
  ServiceFilter,
  StatusFilter,
} from "./webhookTypes";
import { filterWebhooks } from "./webhookUtils";

export function useWebhooksController({
  data,
  onRefresh,
}: {
  data: DashboardData | null;
  onRefresh: () => void;
}) {
  const [search, setSearch] = React.useState("");
  const [serviceFilter, setServiceFilter] =
    React.useState<ServiceFilter>("all");
  const [statusFilter, setStatusFilter] = React.useState<StatusFilter>("all");
  const [dialogOpen, setDialogOpen] = React.useState(false);
  const [form, setForm] = React.useState<WebhookConfig>(createDefaultWebhook);
  const [step, setStep] = React.useState<DialogStep>("basics");
  const [deliveries, setDeliveries] = React.useState<
    WebhookDeliveryAttempt[]
  >([]);
  const [saving, setSaving] = React.useState(false);
  const [testing, setTesting] = React.useState(false);
  const [pendingToggleIds, setPendingToggleIds] = React.useState<
    ReadonlySet<number>
  >(new Set());
  const [enabledOverrides, setEnabledOverrides] = React.useState<
    Record<number, boolean>
  >({});
  const [testResult, setTestResult] =
    React.useState<WebhookTestResponse | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  const webhooks = data?.webhooks ?? [];
  React.useEffect(() => {
    setEnabledOverrides((current) => {
      let changed = false;
      const next = { ...current };
      for (const webhook of webhooks) {
        if (webhook.id != null && current[webhook.id] === webhook.enabled) {
          delete next[webhook.id];
          changed = true;
        }
      }
      return changed ? next : current;
    });
  }, [webhooks]);

  const displayedWebhooks = React.useMemo(
    () =>
      webhooks.map((webhook) =>
        webhook.id != null && enabledOverrides[webhook.id] !== undefined
          ? { ...webhook, enabled: enabledOverrides[webhook.id] }
          : webhook,
      ),
    [enabledOverrides, webhooks],
  );
  const filtered = React.useMemo(
    () => filterWebhooks(displayedWebhooks, search, serviceFilter, statusFilter),
    [displayedWebhooks, search, serviceFilter, statusFilter],
  );

  const loadDeliveries = React.useCallback(async (id: number) => {
    try {
      setDeliveries(await providerApi.webhookDeliveries(id));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  const openCreateDialog = React.useCallback(() => {
    const webhook = createDefaultWebhook();
    setForm(webhook);
    setStep("basics");
    setTestResult(null);
    setDeliveries([]);
    setError(null);
    setDialogOpen(true);
  }, []);

  const openEditDialog = React.useCallback(
    async (webhook: WebhookConfig) => {
      setForm(webhook);
      setStep("basics");
      setTestResult(null);
      setError(null);
      setDialogOpen(true);
      setDeliveries([]);

      if (webhook.id != null) {
        await loadDeliveries(webhook.id);
      }
    },
    [loadDeliveries],
  );

  const save = React.useCallback(async () => {
    setSaving(true);
    setError(null);

    try {
      const saved =
        form.id == null
          ? await providerApi.createWebhook(form)
          : await providerApi.updateWebhook(form.id, form);
      setForm(saved);
      setDialogOpen(false);
      setTestResult(null);

      if (saved.id != null) {
        await loadDeliveries(saved.id);
      }

      onRefresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }, [form, loadDeliveries, onRefresh]);

  const test = React.useCallback(
    async (webhookId = form.id, eventType = selectedTestEvent(form)) => {
      if (webhookId == null) return;
      setTesting(true);
      setError(null);

      try {
        setTestResult(await providerApi.testWebhook(webhookId, eventType));
        await loadDeliveries(webhookId);
        onRefresh();
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setTesting(false);
      }
    },
    [form, loadDeliveries, onRefresh],
  );

  const openTestDialog = React.useCallback(
    async (webhook: WebhookConfig) => {
      const eventType = selectedTestEvent(webhook);
      setForm(webhook);
      setStep("review");
      setTestResult(null);
      setError(null);
      setDialogOpen(true);
      setDeliveries([]);

      if (webhook.id != null) {
        await loadDeliveries(webhook.id);
        await test(webhook.id, eventType);
      }
    },
    [loadDeliveries, test],
  );

  const remove = React.useCallback(
    async (id: number) => {
      setError(null);

      try {
        await providerApi.deleteWebhook(id);
        setDialogOpen(false);
        onRefresh();
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    },
    [onRefresh],
  );

  const toggleEnabled = React.useCallback(
    async (webhook: WebhookConfig, enabled: boolean) => {
      const webhookId = webhook.id;
      if (webhookId == null) return;

      setError(null);
      setEnabledOverrides((current) => ({ ...current, [webhookId]: enabled }));
      setPendingToggleIds((current) => new Set(current).add(webhookId));

      try {
        await providerApi.updateWebhook(webhookId, { ...webhook, enabled });
        onRefresh();
      } catch (err) {
        setEnabledOverrides((current) => {
          const next = { ...current };
          delete next[webhookId];
          return next;
        });
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setPendingToggleIds((current) => {
          const next = new Set(current);
          next.delete(webhookId);
          return next;
        });
      }
    },
    [onRefresh],
  );

  return {
    deliveries,
    dialogOpen,
    error,
    filtered,
    form,
    pendingToggleIds,
    saving,
    search,
    serviceFilter,
    statusFilter,
    step,
    testing,
    testResult,
    openCreateDialog,
    openEditDialog,
    openTestDialog,
    remove,
    save,
    setDialogOpen,
    setForm,
    setSearch,
    setServiceFilter,
    setStatusFilter,
    setStep,
    test,
    toggleEnabled,
  };
}

function selectedTestEvent(webhook: WebhookConfig): WebhookEventType {
  return webhook.events[0] ?? "alert.fired";
}
