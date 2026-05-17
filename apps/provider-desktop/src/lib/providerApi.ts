import { invoke } from "@tauri-apps/api/core";
import type {
  AlertRule,
  HistoryRange,
  LeaseTerminationResult,
  MetricsHistoryResponse,
  MetricsLatestResponse,
  MonitoringOverview,
  ProviderInfo,
  ProviderServiceStatus,
  ProviderSettings,
  ProviderSummary,
  StreamStatus,
  UpdateProviderPricing,
  UpdateProviderResources,
  VMAccessInfo,
  VMInfo,
  WebhookConfig,
  WebhookDeliveryAttempt,
  WebhookEventType,
  WebhookPreviewRequest,
  WebhookPreviewResponse,
  WebhookTestResponse,
} from "./types";

async function serviceBaseUrl() {
  return invoke<string>("provider_api_base_url");
}

async function serviceWebSocketUrl(path: string) {
  const baseUrl = await serviceBaseUrl();
  const url = new URL(`${baseUrl}${path}`);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.toString();
}

export async function providerAdminToken() {
  return invoke<string>("provider_admin_token");
}

async function parseError(response: Response) {
  const text = await response.text();
  if (!text) return `${response.status} ${response.statusText}`;
  try {
    const payload = JSON.parse(text) as { detail?: unknown; message?: unknown };
    return String(payload.detail ?? payload.message ?? text);
  } catch {
    return text;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const baseUrl = await serviceBaseUrl();
  const token = await providerAdminToken();
  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

function post<T>(path: string, body?: unknown) {
  return request<T>(path, {
    method: "POST",
    body: body == null ? undefined : JSON.stringify(body),
  });
}

function patch<T>(path: string, body?: unknown) {
  return request<T>(path, {
    method: "PATCH",
    body: body == null ? undefined : JSON.stringify(body),
  });
}

function put<T>(path: string, body?: unknown) {
  return request<T>(path, {
    method: "PUT",
    body: body == null ? undefined : JSON.stringify(body),
  });
}

export const providerApi = {
  getServiceStatus: () => invoke<ProviderServiceStatus>("provider_status"),
  adminToken: providerAdminToken,
  providerLiveUrl: () => serviceWebSocketUrl("/provider/live"),
  startProvider: () => invoke<void>("start_provider"),
  stopProvider: () => invoke<void>("stop_provider"),
  info: () => request<ProviderInfo>("/provider/info"),
  providerSettings: () => request<ProviderSettings>("/provider/settings"),
  updateProviderResources: (resources: UpdateProviderResources) =>
    patch<ProviderSettings>("/provider/settings/resources", resources),
  updateProviderPricing: (pricing: UpdateProviderPricing) =>
    patch<ProviderSettings>("/provider/settings/pricing", pricing),
  summary: () => request<ProviderSummary>("/summary"),
  vms: () => request<VMInfo[]>("/vms"),
  vm: (id: string) => request<VMInfo>(`/vms/${encodeURIComponent(id)}`),
  vmAccess: (id: string) =>
    request<VMAccessInfo>(`/vms/${encodeURIComponent(id)}/access`),
  terminateLease: (id: string) =>
    post<LeaseTerminationResult>(
      `/admin/vms/${encodeURIComponent(id)}/terminate-lease`,
    ),
  vmStream: (id: string) =>
    request<StreamStatus>(`/vms/${encodeURIComponent(id)}/stream`),
  streams: () => request<StreamStatus[]>("/payments/streams"),
  monitoringOverview: () => request<MonitoringOverview>("/monitoring/overview"),
  metricsLatest: () =>
    request<MetricsLatestResponse>("/monitoring/metrics/latest"),
  metricsHistory: (range: HistoryRange, vmId?: string) => {
    const params = new URLSearchParams({ range });
    if (vmId) {
      params.set("scope", "vm");
      params.set("vm_id", vmId);
    }
    return request<MetricsHistoryResponse>(
      `/monitoring/metrics/history?${params.toString()}`,
    );
  },
  vmMetricsLatest: (id: string) =>
    request<MetricsLatestResponse>(`/vms/${encodeURIComponent(id)}/metrics/latest`),
  vmMetricsHistory: (id: string, range: HistoryRange) =>
    request<MetricsHistoryResponse>(
      `/vms/${encodeURIComponent(id)}/metrics/history?range=${encodeURIComponent(range)}`,
    ),
  alerts: () => request<MonitoringOverview["active_alerts"]>("/monitoring/alerts"),
  alertRules: () => request<AlertRule[]>("/monitoring/alert-rules"),
  createAlertRule: (rule: AlertRule) =>
    post<AlertRule>("/monitoring/alert-rules", rule),
  webhooks: () => request<WebhookConfig[]>("/monitoring/webhooks"),
  createWebhook: (webhook: WebhookConfig) =>
    post<WebhookConfig>("/monitoring/webhooks", webhook),
  updateWebhook: (id: number, webhook: WebhookConfig) =>
    put<WebhookConfig>(`/monitoring/webhooks/${id}`, webhook),
  deleteWebhook: (id: number) =>
    request<void>(`/monitoring/webhooks/${id}`, { method: "DELETE" }),
  webhookDeliveries: (id: number) =>
    request<WebhookDeliveryAttempt[]>(`/monitoring/webhooks/${id}/deliveries`),
  previewWebhook: (request: WebhookPreviewRequest) =>
    post<WebhookPreviewResponse>("/monitoring/webhooks/preview", request),
  testWebhook: (id: number, eventType: WebhookEventType) =>
    post<WebhookTestResponse>(`/monitoring/webhooks/${id}/test`, {
      event_type: eventType,
    }),
};
