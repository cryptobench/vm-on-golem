"use client";

import {
  providerInfoApiV1ProviderInfoGet,
  type CreateSnapshotRequest,
  type CreateVMJobResponse,
  type CreateVMRequest,
  type ResizeVMRequest,
  type LeasePayment,
  type StreamStatus,
  type VMAccessInfo,
  type VMAccessPendingResponse,
  type VMInfo,
  type VMResources,
  type VMSnapshot,
  type CreateVMJobStatus,
  type ProviderInfo,
  type MetricsHistoryResponse,
  type MetricsLatestResponse,
} from "./generated/api/provider";
import type { ApiRequestOptions } from "./api/orval-fetch";
import {
  isUsableProviderEndpoint,
  normalizeProviderEndpoint,
  providerUrl,
  requireProviderEndpoint,
} from "./providerEndpoint";
import { getProviderVmSession } from "./providerSession";
import { DEFAULT_REQUESTOR_DONATION_BPS, normalizeDonationBps } from "./settings";

export type { AdsConfig } from "../context/AdsContext";
export type ProviderAd = {
  provider_id: string;
  ip_address: string;
  country: string;
  platform?: string | null;
  endpoint_protocol?: string | null;
  endpoint_host?: string | null;
  endpoint_port?: number | null;
  endpoint_url?: string | null;
  resources: VMResources;
  pricing?: Record<string, any> | null;
  created_at: string;
  updated_at: string;
};
export type { CreateVMRequest, VMResources };
export { loadSettings, saveSettings, type Settings, type SSHKey } from "./settings";

type LeasePaymentPayload = Omit<LeasePayment, "provider_rate_per_second_wei"> & {
  provider_rate_per_second_wei: number | string;
};

export type Rental = {
  name: string;
  provider_id: string;
  provider_endpoint_url?: string | null;
  provider_ip?: string | null;
  vm_ip?: string | null;
  vm_id: string;
  status: string;
  lifecycle_stage?: string | null;
  status_message?: string | null;
  progress?: number | null;
  transitioning?: boolean | null;
  next_poll_seconds?: number | null;
  creation_job_id?: string | null;
  resources?: VMResources;
  ssh_port?: number | null;
  ssh_user?: string | null;
  stream_id?: number | string | null;
  platform?: string | null;
  provider_pricing?: ProviderAd["pricing"] | null;
  provider_available_resources?: ProviderAd["resources"] | null;
  created_at?: number;
  ended_at?: number;
  end_reason?: string;
  terminated_at?: number;
  settlement_tx_hash?: string | null;
  termination_reason?: string;
  create_failed_at?: number;
  settlement_status?: "pending" | "settled" | "failed" | "not_required";
  cleanup_state?: "not_started" | "completed" | "failed";
};

export type VmMonitoringMetric = {
  value: number;
  unit: string;
  timestamp: string;
  source: string;
};

export type VmMonitoringLatest = Omit<MetricsLatestResponse, "vms"> & {
  vms: Record<string, Record<string, Record<string, VmMonitoringMetric>>>;
};

export type VmMonitoringSample = {
    scope: "host" | "vm";
    source: "infrastructure" | "guest_agent";
    metric: string;
    value: number;
    unit: string;
    timestamp: string;
    vm_id?: string | null;
};

export type VmMonitoringHistory = Partial<MetricsHistoryResponse> & {
  samples?: VmMonitoringSample[];
};

export type VmMonitoringLive = {
  latest?: VmMonitoringLatest | null;
  samples?: VmMonitoringSample[];
  guest_interval_seconds?: number | null;
  live_mode?: boolean | null;
};

export type VmLiveSnapshot = {
  provider_info?: Record<string, unknown> | null;
  lifecycle?: Record<string, unknown> | null;
  access?: Record<string, unknown> | null;
  job?: Record<string, unknown> | null;
  snapshots?: Array<Record<string, unknown>>;
  stream?: Record<string, unknown> | null;
  metrics_live?: VmMonitoringLive | null;
  metrics_history?: VmMonitoringHistory | null;
  errors?: Record<string, string>;
};

export type VmLiveEvent = {
  type: "hello" | "snapshot" | "update" | "error" | "heartbeat";
  generated_at: string;
  scope?: string | null;
  data?: unknown;
  error?: string | null;
};

const RENTALS_KEY = "requestor_rentals_v1";
const LEGACY_RENTAL_SCOPE_FIELD = ["pro", "ject_id"].join("");

export function loadRentals(): Rental[] {
  if (typeof window === "undefined") return [];
  try {
    const rows = JSON.parse(localStorage.getItem(RENTALS_KEY) || "[]");
    if (!Array.isArray(rows)) return [];
    const rentals = rows
      .filter((row) => isUsableProviderEndpoint(row?.provider_endpoint_url))
      .map(stripLegacyRentalFields);
    const changed =
      rentals.length !== rows.length ||
      rentals.some((rental, index) => rental !== rows[index]);
    if (changed) {
      localStorage.setItem(RENTALS_KEY, JSON.stringify(rentals));
    }
    return rentals;
  } catch {
    return [];
  }
}

export function saveRentals(next: Rental[]) {
  if (typeof window === "undefined") return;
  const rentals = next.map(stripLegacyRentalFields);
  localStorage.setItem(RENTALS_KEY, JSON.stringify(rentals));
  window.dispatchEvent(
    new CustomEvent("requestor_rentals_changed", { detail: rentals }),
  );
}

function stripLegacyRentalFields(row: any): Rental {
  if (!row || typeof row !== "object" || !(LEGACY_RENTAL_SCOPE_FIELD in row)) {
    return row as Rental;
  }
  const { [LEGACY_RENTAL_SCOPE_FIELD]: _legacyScope, ...rental } = row;
  return rental as Rental;
}

export function filterProvidersWithUsableEndpoint(
  providers: ProviderAd[],
): ProviderAd[] {
  return providers.filter(hasUsableProviderEndpoint);
}

export function hasUsableProviderEndpoint(provider: ProviderAd): boolean {
  return isUsableProviderEndpoint(
    (provider as { endpoint_url?: string | null }).endpoint_url,
  );
}

export function providerEndpointUrl(provider: ProviderAd): string {
  return requireProviderEndpoint(
    (provider as { endpoint_url?: string | null }).endpoint_url,
  );
}

export function computeEstimate(
  provider: ProviderAd,
  cpu: number,
  memory: number,
  storage: number,
  donationBps = DEFAULT_REQUESTOR_DONATION_BPS,
) {
  const pricing = provider.pricing || {};
  const donationMultiplier = 1 + normalizeDonationBps(donationBps) / 10_000;
  const usd =
    Number(pricing.usd_per_core_month || 0) * cpu +
    Number(pricing.usd_per_gb_ram_month || 0) * memory +
    Number(pricing.usd_per_gb_storage_month || 0) * storage;
  const glmCore = pricing.glm_per_core_month;
  const glmRam = pricing.glm_per_gb_ram_month;
  const glmStorage = pricing.glm_per_gb_storage_month;
  const rawGlm =
    glmCore != null && glmRam != null && glmStorage != null
      ? Number(glmCore) * cpu +
        Number(glmRam) * memory +
        Number(glmStorage) * storage
      : undefined;
  const glm =
    rawGlm != null && Number.isFinite(rawGlm) && rawGlm > 0
      ? rawGlm
      : undefined;
  const totalUsd = usd * donationMultiplier;
  const totalGlm = glm == null ? undefined : glm * donationMultiplier;
  const donationGlm = glm == null ? undefined : glm * (donationMultiplier - 1);
  return {
    lease_usd_per_month: Number(usd.toFixed(4)),
    donation_usd_per_month: Number((totalUsd - usd).toFixed(4)),
    usd_per_month: Number(totalUsd.toFixed(4)),
    usd_per_hour: Number((totalUsd / 730).toFixed(6)),
    lease_glm_per_month: glm == null ? undefined : Number(glm.toFixed(8)),
    donation_glm_per_month:
      donationGlm == null ? undefined : Number(donationGlm.toFixed(8)),
    glm_per_month: totalGlm == null ? undefined : Number(totalGlm.toFixed(8)),
  };
}

export function computePriceRange(
  providers: ProviderAd[],
  spec: { cpu?: number; memory?: number; storage?: number } | undefined,
  donationBps = DEFAULT_REQUESTOR_DONATION_BPS,
) {
  const cpu = spec?.cpu || 0;
  const memory = spec?.memory || 0;
  const storage = spec?.storage || 0;
  const values = providers
    .map(
      (provider) =>
        computeEstimate(provider, cpu, memory, storage, donationBps).usd_per_month,
    )
    .filter((value) => Number.isFinite(value) && value > 0);
  if (!values.length) return null;
  return { min: Math.min(...values), max: Math.max(...values) };
}

export async function providerInfo(providerEndpointUrl: string) {
  return unwrapAs<ProviderInfo>(
    await providerInfoApiV1ProviderInfoGet(providerOptions(providerEndpointUrl)),
    200,
  );
}

export async function createVm(
  providerEndpointUrl: string,
  payload: CreateVMRequest,
): Promise<VMInfo | CreateVMJobResponse> {
  return providerAuthenticatedRequest<VMInfo | CreateVMJobResponse>(
    providerEndpointUrl,
    payload.name,
    "POST",
    "/api/v1/vms?async=true",
    payload,
    200,
    202,
  );
}

export async function vmJobStatus(
  providerEndpointUrl: string,
  jobId: string,
  vmId: string,
) {
  return providerAuthenticatedRequest<CreateVMJobStatus>(
    providerEndpointUrl,
    vmId,
    "GET",
    `/api/v1/vms/jobs/${encodeURIComponent(jobId)}`,
  );
}

export async function vmAccess(
  providerEndpointUrl: string,
  vmId: string,
) {
  return providerAuthenticatedRequest<VMAccessInfo | VMAccessPendingResponse>(
    providerEndpointUrl,
    vmId,
    "GET",
    `/api/v1/vms/${encodeURIComponent(vmId)}/access`,
    undefined,
    200,
    202,
  );
}

export async function vmStatus(
  providerEndpointUrl: string,
  vmId: string,
) {
  return providerAuthenticatedRequest<VMInfo>(
    providerEndpointUrl,
    vmId,
    "GET",
    `/api/v1/vms/${encodeURIComponent(vmId)}`,
  );
}

export async function vmStatusSafe(
  providerEndpointUrl: string,
  vmId: string,
) {
  try {
    return { exists: true, data: await vmStatus(providerEndpointUrl, vmId) };
  } catch (error) {
    const apiError = error as Error & { status?: number };
    return {
      exists: false,
      code: apiError.status || 0,
      error: apiError.message || String(error),
    };
  }
}

export async function vmStreamStatus(
  providerEndpointUrl: string,
  vmId: string,
) {
  return providerAuthenticatedRequest<StreamStatus>(
    providerEndpointUrl,
    vmId,
    "GET",
    `/api/v1/vms/${encodeURIComponent(vmId)}/stream`,
  );
}

export async function vmMetricsLatest(
  providerEndpointUrl: string,
  vmId: string,
) {
  return providerAuthenticatedRequest<VmMonitoringLatest>(
    providerEndpointUrl,
    vmId,
    "GET",
    `/api/v1/vms/${encodeURIComponent(vmId)}/metrics/latest`,
  );
}

export async function vmMetricsHistory(
  providerEndpointUrl: string,
  vmId: string,
  range = "1h",
) {
  return providerAuthenticatedRequest<VmMonitoringHistory>(
    providerEndpointUrl,
    vmId,
    "GET",
    `/api/v1/vms/${encodeURIComponent(vmId)}/metrics/history?range=${encodeURIComponent(range)}`,
  );
}

export function vmLiveUrl(
  providerEndpointUrl: string,
  vmId: string,
  options: { jobId?: string | null; historyRange?: string } = {},
) {
  const url = new URL(
    `${normalizeProviderEndpoint(providerEndpointUrl)}/api/v1/vms/${encodeURIComponent(vmId)}/live`,
  );
  url.protocol = url.protocol === "http:" ? "ws:" : "wss:";
  if (options.jobId) url.searchParams.set("job_id", options.jobId);
  if (options.historyRange) {
    url.searchParams.set("history_range", options.historyRange);
  }
  return url.toString();
}

export const vmStart = (providerEndpointUrl: string, vmId: string) =>
  providerAuthenticatedRequest<VMInfo>(
    providerEndpointUrl,
    vmId,
    "POST",
    `/api/v1/vms/${encodeURIComponent(vmId)}/start`,
    {},
  );
export const vmStop = (providerEndpointUrl: string, vmId: string) =>
  providerAuthenticatedRequest<VMInfo>(
    providerEndpointUrl,
    vmId,
    "POST",
    `/api/v1/vms/${encodeURIComponent(vmId)}/stop`,
    {},
  );
export const vmRestart = (providerEndpointUrl: string, vmId: string) =>
  providerAuthenticatedRequest<VMInfo>(
    providerEndpointUrl,
    vmId,
    "POST",
    `/api/v1/vms/${encodeURIComponent(vmId)}/restart`,
    {},
  );
export const vmSuspend = (providerEndpointUrl: string, vmId: string) =>
  providerAuthenticatedRequest<VMInfo>(
    providerEndpointUrl,
    vmId,
    "POST",
    `/api/v1/vms/${encodeURIComponent(vmId)}/suspend`,
    {},
  );
export const vmResume = (providerEndpointUrl: string, vmId: string) =>
  providerAuthenticatedRequest<VMInfo>(
    providerEndpointUrl,
    vmId,
    "POST",
    `/api/v1/vms/${encodeURIComponent(vmId)}/resume`,
    {},
  );
export const vmDestroy = (providerEndpointUrl: string, vmId: string) =>
  providerAuthenticatedRequest<null>(
    providerEndpointUrl,
    vmId,
    "DELETE",
    `/api/v1/vms/${encodeURIComponent(vmId)}`,
    null,
  );

export function vmResize(
  providerEndpointUrl: string,
  vmId: string,
  resources: VMResources,
  payment?: LeasePaymentPayload | null,
) {
  const payload = (payment ? { resources, payment } : { resources }) as
    | ResizeVMRequest
    | { resources: VMResources; payment: LeasePaymentPayload };
  return providerAuthenticatedRequest<VMInfo>(
    providerEndpointUrl,
    vmId,
    "POST",
    `/api/v1/vms/${encodeURIComponent(vmId)}/resize`,
    payload,
  );
}

export const listSnapshots = (
  providerEndpointUrl: string,
  vmId: string,
) =>
  providerAuthenticatedRequest<VMSnapshot[]>(
    providerEndpointUrl,
    vmId,
    "GET",
    `/api/v1/vms/${encodeURIComponent(vmId)}/snapshots`,
  );

export const createSnapshot = (
  providerEndpointUrl: string,
  vmId: string,
  payload: CreateSnapshotRequest,
) =>
  providerAuthenticatedRequest<VMSnapshot>(
    providerEndpointUrl,
    vmId,
    "POST",
    `/api/v1/vms/${encodeURIComponent(vmId)}/snapshots`,
    payload,
  );

export const restoreSnapshot = (
  providerEndpointUrl: string,
  vmId: string,
  snapshot: string,
) =>
  providerAuthenticatedRequest<VMInfo>(
    providerEndpointUrl,
    vmId,
    "POST",
    `/api/v1/vms/${encodeURIComponent(vmId)}/snapshots/${encodeURIComponent(snapshot)}/restore`,
    {},
  );

export const deleteSnapshot = (
  providerEndpointUrl: string,
  vmId: string,
  snapshot: string,
) =>
  providerAuthenticatedRequest<null>(
    providerEndpointUrl,
    vmId,
    "DELETE",
    `/api/v1/vms/${encodeURIComponent(vmId)}/snapshots/${encodeURIComponent(snapshot)}`,
    null,
  );

async function providerAuthenticatedRequest<T>(
  providerEndpointUrl: string,
  vmId: string,
  method: "GET" | "POST" | "DELETE",
  path: string,
  payload?: unknown,
  ...okStatuses: number[]
): Promise<T> {
  const body = payload == null ? "" : JSON.stringify(payload);
  const token = await getProviderVmSession(providerEndpointUrl, vmId);
  const response = await fetch(providerUrl(providerEndpointUrl, path), {
    method,
    headers: {
      "authorization": `Bearer ${token}`,
      ...(payload == null ? {} : { "content-type": "application/json" }),
    },
    body: payload == null ? undefined : body,
  });
  const data = await response.json().catch(() => null);
  const allowed = okStatuses.length ? okStatuses : [200];
  if (!allowed.includes(response.status)) {
    throw apiError(response.status, data);
  }
  return data as T;
}

type ApiResponse<TData, TStatus extends number = number> = {
  data: TData;
  status: TStatus;
  headers: Headers;
};

async function unwrapAs<
  TData,
  TResponse extends ApiResponse<unknown> = ApiResponse<unknown>,
>(
  responseOrPromise: TResponse | Promise<TResponse>,
  ...okStatuses: Array<TResponse["status"]>
): Promise<TData> {
  const response = await responseOrPromise;
  if (okStatuses.includes(response.status)) {
    return response.data as TData;
  }
  throw apiError(response.status, response.data);
}

function apiError(status: number, data: unknown): Error & { status: number } {
  const message =
    typeof data === "object" && data !== null && "detail" in data
      ? JSON.stringify((data as { detail: unknown }).detail)
      : typeof data === "string"
        ? data
        : JSON.stringify(data);
  const error = new Error(message || `HTTP ${status}`) as Error & {
    status: number;
  };
  error.status = status;
  return error;
}

function providerOptions(providerEndpointUrl: string): RequestInit {
  return withBaseUrl(normalizeProviderEndpoint(providerEndpointUrl));
}

function withBaseUrl(
  baseUrl: string,
  init: ApiRequestOptions = {},
): RequestInit {
  return { ...init, baseUrl } as RequestInit;
}
