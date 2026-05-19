import React from "react";
import {
  Button,
  Card,
  CardBody,
  DataTable,
  FormField,
  PageHeader,
  Select,
  StatCard,
  StatusBadge,
  Input,
  ToggleSwitch,
} from "@golem/ui";
import { RiAlertLine, RiBellLine, RiCheckboxCircleLine, RiCloseLine } from "@remixicon/react";
import { EndpointErrors, LoadingGrid } from "../../components/StateViews";
import { alertTone, enabledRules, severityCount } from "../../lib/derived";
import { EMPTY_VALUE, titleCase } from "../../lib/format";
import { providerApi } from "../../lib/providerApi";
import type { AlertRule } from "../../lib/types";
import type { DashboardData } from "../../lib/useProviderData";

const DEFAULT_RULE: AlertRule = {
  id: null,
  name: "High CPU",
  metric: "cpu_percent",
  scope: "vm",
  source: "guest_agent",
  operator: ">",
  threshold: 90,
  duration_seconds: 300,
  severity: "warning",
  enabled: true,
};

export function AlertsPage({
  data,
  loading,
  onRefresh,
}: {
  data: DashboardData | null;
  loading: boolean;
  onRefresh: () => void;
}) {
  const [rule, setRule] = React.useState<AlertRule>(DEFAULT_RULE);
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  if (loading && !data) return <LoadingGrid />;

  const alerts = data?.alerts ?? [];
  const rules = data?.alertRules ?? [];

  const saveRule = async () => {
    setSaving(true);
    setError(null);
    try {
      await providerApi.createAlertRule(rule);
      setRule(DEFAULT_RULE);
      onRefresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Alerts"
        description="Track active issues and configure alert rules."
      />
      <EndpointErrors errors={{ ...(data?.errors ?? {}), ...(error ? { createRule: error } : {}) }} />

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Active Alerts" value={alerts.length} detail="Across all resources" icon={<RiBellLine className="h-5 w-5" />} tone="warning" />
        <StatCard label="Warning Alerts" value={severityCount(alerts, "warning")} detail="Requires attention" icon={<RiAlertLine className="h-5 w-5" />} tone="warning" />
        <StatCard label="Critical Alerts" value={severityCount(alerts, "critical")} detail="Immediate action" icon={<RiCloseLine className="h-5 w-5" />} tone="danger" />
        <StatCard label="Alert Rules Enabled" value={enabledRules(rules)} detail="Across all scopes" icon={<RiCheckboxCircleLine className="h-5 w-5" />} tone="success" />
      </div>

      <div className="grid gap-4 xl:grid-cols-[1fr_1fr_0.75fr]">
        <Card>
          <CardBody className="space-y-4">
            <h2 className="text-base font-semibold text-text-primary">Active Alerts</h2>
            {alerts.length === 0 ? (
              <div className="text-sm text-text-secondary">No active alerts</div>
            ) : (
              alerts.map((alert) => (
                <div
                  key={`${alert.name}-${alert.vm_id ?? alert.scope}`}
                  className="rounded-lg border border-border px-4 py-4"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="font-semibold text-text-primary">{alert.name}</div>
                    <StatusBadge label={titleCase(alert.severity)} tone={alertTone(alert.severity)} />
                  </div>
                  <dl className="mt-4 grid grid-cols-[7rem_1fr] gap-3 text-sm">
                    <dt className="text-text-secondary">Metric</dt>
                    <dd>{alert.metric}</dd>
                    <dt className="text-text-secondary">Scope</dt>
                    <dd>{alert.scope}</dd>
                    <dt className="text-text-secondary">VM ID</dt>
                    <dd>{alert.vm_id ?? EMPTY_VALUE}</dd>
                    <dt className="text-text-secondary">Value</dt>
                    <dd>{alert.value ?? EMPTY_VALUE}</dd>
                    <dt className="text-text-secondary">Threshold</dt>
                    <dd>{alert.threshold ?? EMPTY_VALUE}</dd>
                    <dt className="text-text-secondary">Message</dt>
                    <dd>{alert.message ?? EMPTY_VALUE}</dd>
                  </dl>
                </div>
              ))
            )}
          </CardBody>
        </Card>

        <Card>
          <CardBody className="p-0">
            <div className="p-4">
              <h2 className="text-base font-semibold text-text-primary">Alert Rules</h2>
            </div>
            <DataTable
              rows={rules}
              getRowKey={(item) => item.id ?? item.name}
              empty="No alert rules configured"
              columns={[
                { key: "name", header: "Name", render: (item) => <span className="font-medium">{item.name}</span> },
                { key: "metric", header: "Metric", render: (item) => `${item.metric} - ${item.scope}` },
                { key: "severity", header: "Severity", render: (item) => <StatusBadge label={titleCase(item.severity)} tone={alertTone(item.severity)} /> },
                { key: "enabled", header: "Enabled", render: (item) => item.enabled ? "Yes" : "No" },
              ]}
            />
          </CardBody>
        </Card>

        <Card>
          <CardBody className="space-y-4">
            <h2 className="text-base font-semibold text-text-primary">Create Alert Rule</h2>
            <FormField label="Name">
              <Input value={rule.name} onChange={(event) => setRule({ ...rule, name: event.target.value })} />
            </FormField>
            <FormField label="Metric">
              <Select value={rule.metric} onChange={(event) => setRule({ ...rule, metric: event.target.value })}>
                <option value="cpu_percent">cpu_percent</option>
                <option value="memory_percent">memory_percent</option>
                <option value="disk_percent">disk_percent</option>
                <option value="stream_active">stream_active</option>
                <option value="guest_agent_up">guest_agent_up</option>
              </Select>
            </FormField>
            <FormField label="Scope">
              <Select value={rule.scope} onChange={(event) => setRule({ ...rule, scope: event.target.value as AlertRule["scope"] })}>
                <option value="vm">vm</option>
                <option value="host">host</option>
              </Select>
            </FormField>
            <FormField label="Source">
              <Select value={rule.source} onChange={(event) => setRule({ ...rule, source: event.target.value as AlertRule["source"] })}>
                <option value="guest_agent">guest_agent</option>
                <option value="infrastructure">infrastructure</option>
              </Select>
            </FormField>
            <div className="grid grid-cols-2 gap-3">
              <FormField label="Operator">
                <Select value={rule.operator} onChange={(event) => setRule({ ...rule, operator: event.target.value })}>
                  <option value=">">&gt;</option>
                  <option value="<">&lt;</option>
                  <option value="==">==</option>
                </Select>
              </FormField>
              <FormField label="Threshold">
                <Input type="number" value={rule.threshold} onChange={(event) => setRule({ ...rule, threshold: Number(event.target.value) })} />
              </FormField>
            </div>
            <FormField label="Duration (seconds)">
              <Input type="number" value={rule.duration_seconds} onChange={(event) => setRule({ ...rule, duration_seconds: Number(event.target.value) })} />
            </FormField>
            <FormField label="Severity">
              <Select value={rule.severity} onChange={(event) => setRule({ ...rule, severity: event.target.value })}>
                <option value="warning">Warning</option>
                <option value="critical">Critical</option>
              </Select>
            </FormField>
            <div className="flex items-center justify-between text-sm text-text-secondary">
              Enabled
              <ToggleSwitch checked={rule.enabled} onChange={(enabled) => setRule({ ...rule, enabled })} label="Rule enabled" />
            </div>
            <Button className="w-full" busy={saving} disabled={!rule.name || !rule.metric} onClick={saveRule}>
              Create Rule
            </Button>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
