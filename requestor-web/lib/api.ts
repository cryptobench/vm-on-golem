"use client";

import {
  listAdvertisementsApiV1AdvertisementsGet,
  type AdvertisementResponse,
  type ListAdvertisementsApiV1AdvertisementsGetParams,
} from "./generated/api/central-discovery";
import {
  createVmApiV1VmsPost,
  getCreateJobApiV1VmsJobsJobIdGet,
  getVmAccessApiV1VmsRequestorNameAccessGet,
  getVmStatusApiV1VmsRequestorNameGet,
  getVmStreamStatusApiV1VmsRequestorNameStreamGet,
  listSnapshotsApiV1VmsRequestorNameSnapshotsGet,
  providerInfoApiV1ProviderInfoGet,
  providerSummaryApiV1SummaryGet,
  type CreateSnapshotRequest,
  type CreateVMJobResponse,
  type CreateVMRequest,
  type ResizeVMRequest,
  type StreamStatus,
  type VMAccessInfo,
  type VMAccessPendingResponse,
  type VMInfo,
  type VMResources,
  type VMSnapshot,
  type CreateVMJobStatus,
  type ProviderInfo,
  type ProviderSummary,
} from "./generated/api/provider";
import type { AdsConfig } from "../context/AdsContext";
import type { ApiRequestOptions } from "./api/orval-fetch";
import { getRequestorRuntimeConfig } from "./runtimeConfig";
import { getPaymentsSigner } from "./walletClient";

export type { AdsConfig } from "../context/AdsContext";
export type ProviderAd = AdvertisementResponse;
export type { CreateVMRequest, VMResources, ProviderSummary };
export { loadSettings, saveSettings, type Settings, type SSHKey } from "./settings";

export type Rental = {
  name: string;
  provider_id: string;
  provider_endpoint_url?: string | null;
  provider_ip?: string | null;
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
  project_id?: string;
  platform?: string | null;
  created_at?: number;
  ended_at?: number;
  end_reason?: string;
  terminated_at?: number;
  settlement_tx_hash?: string | null;
  termination_reason?: string;
  create_failed_at?: number;
  settlement_status?: "pending" | "settled" | "failed" | "not_required";
};

export type VmMonitoringLatest = {
  host: Record<string, unknown>;
  vms: Record<
    string,
    Record<
      string,
      Record<
        string,
        { value: number; unit: string; timestamp: string; source: string }
      >
    >
  >;
  generated_at: string;
};

export type VmMonitoringHistory = {
  samples: Array<{
    scope: "host" | "vm";
    source: "infrastructure" | "guest_agent";
    metric: string;
    value: number;
    unit: string;
    timestamp: string;
    vm_id?: string | null;
  }>;
};

export type VmLiveSnapshot = {
  provider_info?: Record<string, unknown> | null;
  lifecycle?: Record<string, unknown> | null;
  access?: Record<string, unknown> | null;
  job?: Record<string, unknown> | null;
  snapshots?: Array<Record<string, unknown>>;
  stream?: Record<string, unknown> | null;
  metrics_latest?: VmMonitoringLatest | null;
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

export function loadRentals(): Rental[] {
  if (typeof window === "undefined") return [];
  try {
    const rows = JSON.parse(localStorage.getItem(RENTALS_KEY) || "[]");
    if (!Array.isArray(rows)) return [];
    const rentals = rows.filter((row) =>
      isUsableProviderEndpoint(row?.provider_endpoint_url),
    );
    if (rentals.length !== rows.length) {
      localStorage.setItem(RENTALS_KEY, JSON.stringify(rentals));
    }
    return rentals;
  } catch {
    return [];
  }
}

export function saveRentals(next: Rental[]) {
  if (typeof window === "undefined") return;
  localStorage.setItem(RENTALS_KEY, JSON.stringify(next));
  window.dispatchEvent(
    new CustomEvent("requestor_rentals_changed", { detail: next }),
  );
}

export async function fetchAllProviders(ads: AdsConfig): Promise<ProviderAd[]> {
  const providers = await unwrapAs<ProviderAd[]>(
    await listAdvertisementsApiV1AdvertisementsGet(
      {},
      withBaseUrl(centralDiscoveryOrigin(ads)),
    ),
    200,
  );
  return filterProvidersWithUsableEndpoint(providers);
}

export async function fetchProviders(
  query: Partial<{
    cpu: number;
    memory: number;
    storage: number;
    country: string;
    platform: string;
  }>,
  ads: AdsConfig,
): Promise<ProviderAd[]> {
  const params: ListAdvertisementsApiV1AdvertisementsGetParams = {};
  if (query.cpu != null) params.cpu = query.cpu;
  if (query.memory != null) params.memory = query.memory;
  if (query.storage != null) params.storage = query.storage;
  if (query.country) params.country = query.country;
  if (query.platform) params.platform = query.platform;

  const providers = await unwrapAs<ProviderAd[]>(
    await listAdvertisementsApiV1AdvertisementsGet(
      params,
      withBaseUrl(centralDiscoveryOrigin(ads)),
    ),
    200,
  );
  return filterProvidersWithUsableEndpoint(providers);
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
) {
  const pricing = provider.pricing || {};
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
  return {
    usd_per_month: Number(usd.toFixed(4)),
    usd_per_hour: Number((usd / 730).toFixed(6)),
    glm_per_month: glm == null ? undefined : Number(glm.toFixed(8)),
  };
}

export function computePriceRange(
  providers: ProviderAd[],
  spec: { cpu?: number; memory?: number; storage?: number } | undefined,
) {
  const cpu = spec?.cpu || 0;
  const memory = spec?.memory || 0;
  const storage = spec?.storage || 0;
  const values = providers
    .map(
      (provider) =>
        computeEstimate(provider, cpu, memory, storage).usd_per_month,
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

export async function providerSummary(providerEndpointUrl: string) {
  return unwrapAs<ProviderSummary>(
    await providerSummaryApiV1SummaryGet(providerOptions(providerEndpointUrl)),
    200,
  );
}

export async function createVm(
  providerEndpointUrl: string,
  payload: CreateVMRequest,
): Promise<VMInfo | CreateVMJobResponse> {
  if ((payload as any).payment) {
    const path = "/api/v1/vms";
    const body = JSON.stringify(payload);
    const headers = await signedProviderActionHeaders("POST", path, body);
    const response = await fetch(providerUrl(providerEndpointUrl, `${path}?async=true`), {
      method: "POST",
      headers: { "content-type": "application/json", ...headers },
      body,
    });
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      throw apiError(response.status, data);
    }
    return data as VMInfo | CreateVMJobResponse;
  }
  return unwrapAs<VMInfo | CreateVMJobResponse>(
    await createVmApiV1VmsPost(
      payload,
      { async: true },
      providerOptions(providerEndpointUrl),
    ),
    200,
    202,
  );
}

async function signedProviderActionHeaders(method: string, path: string, body: string) {
  const signer = await getPaymentsSigner();
  const requestor = await signer.getAddress();
  const deadline = Math.floor(Date.now() / 1000) + 300;
  const nonce = String(Date.now()) + "-" + Math.random().toString(16).slice(2);
  const bodyHash = await sha256Hex(body);
  const signature = await signer.signTypedData(
    { name: "GolemProviderAction", version: "2" },
    {
      ProviderAction: [
        { name: "requestor", type: "address" },
        { name: "method", type: "string" },
        { name: "path", type: "string" },
        { name: "bodyHash", type: "bytes32" },
        { name: "nonce", type: "string" },
        { name: "deadline", type: "uint256" },
      ],
    },
    { requestor, method: method.toUpperCase(), path, bodyHash, nonce, deadline },
  );
  return {
    "x-golem-requestor": requestor,
    "x-golem-signature": signature,
    "x-golem-nonce": nonce,
    "x-golem-deadline": String(deadline),
  };
}

async function sha256Hex(text: string) {
  const data = new TextEncoder().encode(text);
  const digest = await crypto.subtle.digest("SHA-256", data);
  return `0x${Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("")}`;
}

export async function vmJobStatus(
  providerEndpointUrl: string,
  jobId: string,
) {
  return unwrapAs<CreateVMJobStatus>(
    await getCreateJobApiV1VmsJobsJobIdGet(
      jobId,
      providerOptions(providerEndpointUrl),
    ),
    200,
  );
}

export async function vmAccess(
  providerEndpointUrl: string,
  vmId: string,
) {
  return unwrapAs<VMAccessInfo | VMAccessPendingResponse>(
    await getVmAccessApiV1VmsRequestorNameAccessGet(
      vmId,
      providerOptions(providerEndpointUrl),
    ),
    200,
    202,
  );
}

export async function vmStatus(
  providerEndpointUrl: string,
  vmId: string,
) {
  return unwrapAs<VMInfo>(
    await getVmStatusApiV1VmsRequestorNameGet(
      vmId,
      providerOptions(providerEndpointUrl),
    ),
    200,
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
  return unwrapAs<StreamStatus>(
    await getVmStreamStatusApiV1VmsRequestorNameStreamGet(
      vmId,
      providerOptions(providerEndpointUrl),
    ),
    200,
  );
}

export async function vmMetricsLatest(
  providerEndpointUrl: string,
  vmId: string,
) {
  return providerFetch<VmMonitoringLatest>(
    providerEndpointUrl,
    `/api/v1/vms/${encodeURIComponent(vmId)}/metrics/latest`,
  );
}

export async function vmMetricsHistory(
  providerEndpointUrl: string,
  vmId: string,
  range = "1h",
) {
  return providerFetch<VmMonitoringHistory>(
    providerEndpointUrl,
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
  signedProviderRequest<VMInfo>(
    providerEndpointUrl,
    "POST",
    `/api/v1/vms/${encodeURIComponent(vmId)}/start`,
    {},
  );
export const vmStop = (providerEndpointUrl: string, vmId: string) =>
  signedProviderRequest<VMInfo>(
    providerEndpointUrl,
    "POST",
    `/api/v1/vms/${encodeURIComponent(vmId)}/stop`,
    {},
  );
export const vmRestart = (providerEndpointUrl: string, vmId: string) =>
  signedProviderRequest<VMInfo>(
    providerEndpointUrl,
    "POST",
    `/api/v1/vms/${encodeURIComponent(vmId)}/restart`,
    {},
  );
export const vmSuspend = (providerEndpointUrl: string, vmId: string) =>
  signedProviderRequest<VMInfo>(
    providerEndpointUrl,
    "POST",
    `/api/v1/vms/${encodeURIComponent(vmId)}/suspend`,
    {},
  );
export const vmResume = (providerEndpointUrl: string, vmId: string) =>
  signedProviderRequest<VMInfo>(
    providerEndpointUrl,
    "POST",
    `/api/v1/vms/${encodeURIComponent(vmId)}/resume`,
    {},
  );
export const vmDestroy = (providerEndpointUrl: string, vmId: string) =>
  signedProviderRequest<null>(
    providerEndpointUrl,
    "DELETE",
    `/api/v1/vms/${encodeURIComponent(vmId)}`,
    null,
  );

export function vmResize(
  providerEndpointUrl: string,
  vmId: string,
  resources: VMResources,
) {
  const payload: ResizeVMRequest = { resources };
  return signedProviderRequest<VMInfo>(
    providerEndpointUrl,
    "POST",
    `/api/v1/vms/${encodeURIComponent(vmId)}/resize`,
    payload,
  );
}

export const listSnapshots = (
  providerEndpointUrl: string,
  vmId: string,
) =>
  unwrapAs<VMSnapshot[]>(
    listSnapshotsApiV1VmsRequestorNameSnapshotsGet(
      vmId,
      providerOptions(providerEndpointUrl),
    ),
    200,
  );

export const createSnapshot = (
  providerEndpointUrl: string,
  vmId: string,
  payload: CreateSnapshotRequest,
) =>
  signedProviderRequest<VMSnapshot>(
    providerEndpointUrl,
    "POST",
    `/api/v1/vms/${encodeURIComponent(vmId)}/snapshots`,
    payload,
  );

export const restoreSnapshot = (
  providerEndpointUrl: string,
  vmId: string,
  snapshot: string,
) =>
  signedProviderRequest<VMInfo>(
    providerEndpointUrl,
    "POST",
    `/api/v1/vms/${encodeURIComponent(vmId)}/snapshots/${encodeURIComponent(snapshot)}/restore`,
    {},
  );

export const deleteSnapshot = (
  providerEndpointUrl: string,
  vmId: string,
  snapshot: string,
) =>
  signedProviderRequest<null>(
    providerEndpointUrl,
    "DELETE",
    `/api/v1/vms/${encodeURIComponent(vmId)}/snapshots/${encodeURIComponent(snapshot)}`,
    null,
  );

async function signedProviderRequest<T>(
  providerEndpointUrl: string,
  method: "POST" | "DELETE",
  path: string,
  payload: unknown,
): Promise<T> {
  const body = payload === null ? "" : JSON.stringify(payload);
  const headers = await signedProviderActionHeaders(method, path, body);
  const response = await fetch(providerUrl(providerEndpointUrl, path), {
    method,
    headers:
      payload === null
        ? headers
        : { "content-type": "application/json", ...headers },
    body: payload === null ? undefined : body,
  });
  const data = await response.json().catch(() => null);
  if (!response.ok) {
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

function centralDiscoveryOrigin(ads: AdsConfig): string {
  return ads.discovery_url.replace(/\/api\/v1\/?$/, "").replace(/\/$/, "");
}

function providerOptions(providerEndpointUrl: string): RequestInit {
  return withBaseUrl(normalizeProviderEndpoint(providerEndpointUrl));
}

async function providerFetch<TData>(
  providerEndpointUrl: string,
  path: string,
): Promise<TData> {
  const response = await fetch(providerUrl(providerEndpointUrl, path), {
    cache: "no-store",
  });
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw apiError(response.status, data);
  }
  return data as TData;
}

function providerUrl(providerEndpointUrl: string, path: string): string {
  return `${normalizeProviderEndpoint(providerEndpointUrl)}${path}`;
}

function normalizeProviderEndpoint(endpointUrl: string): string {
  return requireProviderEndpoint(endpointUrl).replace(/\/$/, "");
}

function requireProviderEndpoint(endpointUrl: unknown): string {
  const value = typeof endpointUrl === "string" ? endpointUrl.trim() : "";
  if (!isUsableProviderEndpoint(value)) {
    throw new Error("Provider endpoint unavailable");
  }
  return value;
}

function isUsableProviderEndpoint(endpointUrl: unknown): endpointUrl is string {
  if (typeof endpointUrl !== "string" || !endpointUrl.trim()) return false;
  try {
    const url = new URL(endpointUrl);
    if (url.protocol === "https:") return true;
    return (
      url.protocol === "http:" &&
      getRequestorRuntimeConfig().golemEnvironment === "development"
    );
  } catch {
    return false;
  }
}

function withBaseUrl(
  baseUrl: string,
  init: ApiRequestOptions = {},
): RequestInit {
  return { ...init, baseUrl } as RequestInit;
}
