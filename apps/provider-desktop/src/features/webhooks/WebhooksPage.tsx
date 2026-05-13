import React from "react";
import {
  ActionMenu,
  Button,
  Card,
  CardBody,
  DataTable,
  FormField,
  PageHeader,
  StatCard,
  StatusBadge,
  TextInput,
  ToggleSwitch,
} from "@golem/ui";
import { RiCalendarLine, RiCheckboxCircleLine, RiErrorWarningLine, RiPlayLine, RiSaveLine, RiWebhookLine } from "@remixicon/react";
import { EndpointErrors, LoadingGrid } from "../../components/StateViews";
import { EMPTY_VALUE, formatDateTime } from "../../lib/format";
import { providerApi } from "../../lib/providerApi";
import type { WebhookConfig, WebhookTestResponse } from "../../lib/types";
import type { DashboardData } from "../../lib/useProviderData";

const DEFAULT_WEBHOOK: WebhookConfig = {
  id: null,
  name: "Ops alerts",
  url: "",
  enabled: true,
  last_status: null,
  last_error: null,
  last_delivered_at: null,
};

export function WebhooksPage({
  data,
  loading,
  onRefresh,
}: {
  data: DashboardData | null;
  loading: boolean;
  onRefresh: () => void;
}) {
  const [form, setForm] = React.useState<WebhookConfig>(DEFAULT_WEBHOOK);
  const [saving, setSaving] = React.useState(false);
  const [testingId, setTestingId] = React.useState<number | null>(null);
  const [testResult, setTestResult] = React.useState<WebhookTestResponse | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  if (loading && !data) return <LoadingGrid />;

  const webhooks = data?.webhooks ?? [];
  const lastDelivered = webhooks
    .map((webhook) => webhook.last_delivered_at)
    .filter(Boolean)
    .sort();
  const lastDeliveredAt = lastDelivered.length
    ? lastDelivered[lastDelivered.length - 1]
    : null;

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      const created = await providerApi.createWebhook(form);
      setForm(DEFAULT_WEBHOOK);
      setTestResult(null);
      if (created.id != null) setTestingId(created.id);
      onRefresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };

  const test = async (id: number) => {
    setTestingId(id);
    setError(null);
    try {
      setTestResult(await providerApi.testWebhook(id));
      onRefresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Webhooks"
        description="Deliver provider alerts to your external systems."
      />
      <EndpointErrors errors={{ ...(data?.errors ?? {}), ...(error ? { webhook: error } : {}) }} />

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Total Webhooks" value={webhooks.length} icon={<RiWebhookLine className="h-5 w-5" />} tone="primary" />
        <StatCard label="Enabled" value={webhooks.filter((webhook) => webhook.enabled).length} icon={<RiCheckboxCircleLine className="h-5 w-5" />} tone="success" />
        <StatCard label="Last Delivery" value={formatDateTime(lastDeliveredAt)} icon={<RiCalendarLine className="h-5 w-5" />} tone="primary" />
        <StatCard label="Failed Tests" value={webhooks.filter((webhook) => webhook.last_status === "failed").length} icon={<RiErrorWarningLine className="h-5 w-5" />} tone="danger" />
      </div>

      <div className="grid gap-4 xl:grid-cols-[1fr_0.42fr]">
        <Card>
          <CardBody className="p-0">
            <DataTable
              rows={webhooks}
              getRowKey={(webhook) => webhook.id ?? webhook.name}
              empty="No webhooks configured"
              columns={[
                { key: "name", header: "Name", render: (webhook) => webhook.name },
                {
                  key: "url",
                  header: "URL",
                  render: (webhook) => (
                    <span className="text-primary">{webhook.url}</span>
                  ),
                },
                {
                  key: "enabled",
                  header: "Enabled",
                  render: (webhook) => (
                    <ToggleSwitch
                      checked={webhook.enabled}
                      onChange={() => undefined}
                      disabled
                      label={`${webhook.name} enabled`}
                    />
                  ),
                },
                {
                  key: "status",
                  header: "Last Status",
                  render: (webhook) => (
                    <StatusBadge
                      label={webhook.last_status ?? EMPTY_VALUE}
                      tone={webhook.last_status === "success" ? "success" : webhook.last_status ? "danger" : "neutral"}
                    />
                  ),
                },
                { key: "delivered", header: "Last Delivered At", render: (webhook) => formatDateTime(webhook.last_delivered_at) },
                {
                  key: "actions",
                  header: "",
                  render: (webhook) => (
                    <ActionMenu
                      items={[
                        {
                          label: "Test webhook",
                          disabled: webhook.id == null,
                          onSelect: () => {
                            if (webhook.id != null) void test(webhook.id);
                          },
                        },
                      ]}
                    />
                  ),
                },
              ]}
            />
          </CardBody>
        </Card>

        <Card>
          <CardBody className="space-y-5">
            <h2 className="text-base font-semibold text-text-primary">Add Webhook</h2>
            <FormField label="Name">
              <TextInput value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
            </FormField>
            <FormField label="URL">
              <TextInput value={form.url} placeholder="https://example.com/golem-alerts" onChange={(event) => setForm({ ...form, url: event.target.value })} />
            </FormField>
            <div className="flex items-center justify-between text-sm text-text-secondary">
              Enabled
              <ToggleSwitch checked={form.enabled} onChange={(enabled) => setForm({ ...form, enabled })} label="Webhook enabled" />
            </div>
            <Button className="w-full" busy={saving} disabled={!form.name || !form.url} onClick={save}>
              <RiSaveLine className="h-4 w-4" aria-hidden />
              Save Webhook
            </Button>
            <Button
              className="w-full"
              variant="secondary"
              disabled={testingId == null}
              onClick={() => {
                if (testingId != null) void test(testingId);
              }}
            >
              <RiPlayLine className="h-4 w-4" aria-hidden />
              Test Webhook
            </Button>
            {testResult ? (
              <div className="rounded-lg border border-border p-4">
                <div className="flex items-center justify-between">
                  <h3 className="font-semibold text-text-primary">Test Result</h3>
                  <StatusBadge
                    label={testResult.ok ? "Success" : "Failed"}
                    tone={testResult.ok ? "success" : "danger"}
                  />
                </div>
                <dl className="mt-4 grid grid-cols-[1fr_1fr] gap-3 text-sm">
                  <dt className="text-text-secondary">ok</dt>
                  <dd className="text-right">{String(testResult.ok)}</dd>
                  <dt className="text-text-secondary">status</dt>
                  <dd className="text-right">{testResult.status ?? EMPTY_VALUE}</dd>
                  <dt className="text-text-secondary">error</dt>
                  <dd className="text-right">{testResult.error ?? EMPTY_VALUE}</dd>
                </dl>
              </div>
            ) : null}
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
