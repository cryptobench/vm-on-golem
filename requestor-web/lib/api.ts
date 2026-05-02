"use client";

import {
  listAdvertisementsApiV1AdvertisementsGet,
  type AdvertisementResponse,
  type ListAdvertisementsApiV1AdvertisementsGetParams,
} from "./generated/api/central-discovery";
import {
  createSnapshotApiV1VmsRequestorNameSnapshotsPost,
  createVmApiV1VmsPost,
  deleteSnapshotApiV1VmsRequestorNameSnapshotsSnapshotNameDelete,
  deleteVmApiV1VmsRequestorNameDelete,
  getCreateJobApiV1VmsJobsJobIdGet,
  getVmAccessApiV1VmsRequestorNameAccessGet,
  getVmStatusApiV1VmsRequestorNameGet,
  getVmStreamStatusApiV1VmsRequestorNameStreamGet,
  listSnapshotsApiV1VmsRequestorNameSnapshotsGet,
  providerInfoApiV1ProviderInfoGet,
  resizeVmApiV1VmsRequestorNameResizePost,
  restartVmApiV1VmsRequestorNameRestartPost,
  restoreSnapshotApiV1VmsRequestorNameSnapshotsSnapshotNameRestorePost,
  resumeVmApiV1VmsRequestorNameResumePost,
  startVmApiV1VmsRequestorNameStartPost,
  stopVmApiV1VmsRequestorNameStopPost,
  suspendVmApiV1VmsRequestorNameSuspendPost,
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
} from "./generated/api/provider";
import type { AdsConfig } from "../context/AdsContext";

export type { AdsConfig } from "../context/AdsContext";
export type ProviderAd = AdvertisementResponse;
export type { CreateVMRequest, VMResources };

export type SSHKey = {
  id: string;
  name: string;
  value: string;
  public_key?: string;
};

export type Settings = {
  ssh_public_key?: string;
  ssh_keys?: SSHKey[];
  default_ssh_key_id?: string;
  stream_payment_address?: string;
  glm_token_address?: string;
  display_currency?: "fiat" | "token";
  show_terminated?: boolean;
  show_ended_streams?: boolean;
};

export type Rental = {
  name: string;
  provider_id: string;
  provider_ip?: string | null;
  vm_id: string;
  status: string;
  resources?: VMResources;
  ssh_port?: number | null;
  stream_id?: number | string | null;
  project_id?: string;
  platform?: string | null;
  created_at?: number;
  ended_at?: number;
  end_reason?: string;
};

export type VmMonitoringLatest = {
  host: Record<string, unknown>;
  vms: Record<string, Record<string, Record<string, { value: number; unit: string; timestamp: string; source: string }>>>;
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

const SETTINGS_KEY = "requestor_settings_v1";
const RENTALS_KEY = "requestor_rentals_v1";

export function loadSettings(): Settings {
  if (typeof window === "undefined") return {};
  try {
    return JSON.parse(localStorage.getItem(SETTINGS_KEY) || "{}");
  } catch {
    return {};
  }
}

export function saveSettings(next: Partial<Settings>) {
  if (typeof window === "undefined") return;
  const settings = { ...loadSettings(), ...next };
  localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
  window.dispatchEvent(
    new CustomEvent("requestor_settings_changed", { detail: settings }),
  );
}

export function loadRentals(): Rental[] {
  if (typeof window === "undefined") return [];
  try {
    const rows = JSON.parse(localStorage.getItem(RENTALS_KEY) || "[]");
    return Array.isArray(rows) ? rows : [];
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
  return unwrapAs<ProviderAd[]>(
    await listAdvertisementsApiV1AdvertisementsGet(
      {},
      withBaseUrl(centralDiscoveryOrigin(ads)),
    ),
    200,
  );
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

  return unwrapAs<ProviderAd[]>(
    await listAdvertisementsApiV1AdvertisementsGet(
      params,
      withBaseUrl(centralDiscoveryOrigin(ads)),
    ),
    200,
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
  const glm =
    glmCore != null && glmRam != null && glmStorage != null
      ? Number(glmCore) * cpu + Number(glmRam) * memory + Number(glmStorage) * storage
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
    .map((provider) => computeEstimate(provider, cpu, memory, storage).usd_per_month)
    .filter((value) => Number.isFinite(value) && value > 0);
  if (!values.length) return null;
  return { min: Math.min(...values), max: Math.max(...values) };
}

export async function providerInfo(providerId: string, ads: AdsConfig) {
  return unwrapAs<ProviderInfo>(
    await providerInfoApiV1ProviderInfoGet(providerOptions(providerId, ads)),
    200,
  );
}

export async function createVm(
  providerId: string,
  payload: CreateVMRequest,
  ads: AdsConfig,
) : Promise<VMInfo | CreateVMJobResponse> {
  return unwrapAs<VMInfo | CreateVMJobResponse>(
    await createVmApiV1VmsPost(payload, { async: true }, providerOptions(providerId, ads)),
    200,
    202,
  );
}

export async function vmJobStatus(providerId: string, jobId: string, ads: AdsConfig) {
  return unwrapAs<CreateVMJobStatus>(
    await getCreateJobApiV1VmsJobsJobIdGet(jobId, providerOptions(providerId, ads)),
    200,
  );
}

export async function vmAccess(providerId: string, vmId: string, ads: AdsConfig) {
  return unwrapAs<VMAccessInfo | VMAccessPendingResponse>(
    await getVmAccessApiV1VmsRequestorNameAccessGet(vmId, providerOptions(providerId, ads)),
    200,
    202,
  );
}

export async function vmStatus(providerId: string, vmId: string, ads: AdsConfig) {
  return unwrapAs<VMInfo>(
    await getVmStatusApiV1VmsRequestorNameGet(vmId, providerOptions(providerId, ads)),
    200,
  );
}

export async function vmStatusSafe(providerId: string, vmId: string, ads: AdsConfig) {
  try {
    return { exists: true, data: await vmStatus(providerId, vmId, ads) };
  } catch (error) {
    const apiError = error as Error & { status?: number };
    return {
      exists: false,
      code: apiError.status || 0,
      error: apiError.message || String(error),
    };
  }
}

export async function vmStreamStatus(providerId: string, vmId: string, ads: AdsConfig) {
  return unwrapAs<StreamStatus>(
    await getVmStreamStatusApiV1VmsRequestorNameStreamGet(
      vmId,
      providerOptions(providerId, ads),
    ),
    200,
  );
}

export async function vmMetricsLatest(providerId: string, vmId: string, ads: AdsConfig) {
  return providerFetch<VmMonitoringLatest>(
    providerId,
    `/api/v1/vms/${encodeURIComponent(vmId)}/metrics/latest`,
    ads,
  );
}

export async function vmMetricsHistory(
  providerId: string,
  vmId: string,
  ads: AdsConfig,
  range = "1h",
) {
  return providerFetch<VmMonitoringHistory>(
    providerId,
    `/api/v1/vms/${encodeURIComponent(vmId)}/metrics/history?range=${encodeURIComponent(range)}`,
    ads,
  );
}

export const vmStart = (providerId: string, vmId: string, ads: AdsConfig) =>
  unwrapAs<VMInfo>(
    startVmApiV1VmsRequestorNameStartPost(vmId, providerOptions(providerId, ads)),
    200,
  );
export const vmStop = (providerId: string, vmId: string, ads: AdsConfig) =>
  unwrapAs<VMInfo>(
    stopVmApiV1VmsRequestorNameStopPost(vmId, providerOptions(providerId, ads)),
    200,
  );
export const vmRestart = (providerId: string, vmId: string, ads: AdsConfig) =>
  unwrapAs<VMInfo>(
    restartVmApiV1VmsRequestorNameRestartPost(vmId, providerOptions(providerId, ads)),
    200,
  );
export const vmSuspend = (providerId: string, vmId: string, ads: AdsConfig) =>
  unwrapAs<VMInfo>(
    suspendVmApiV1VmsRequestorNameSuspendPost(vmId, providerOptions(providerId, ads)),
    200,
  );
export const vmResume = (providerId: string, vmId: string, ads: AdsConfig) =>
  unwrapAs<VMInfo>(
    resumeVmApiV1VmsRequestorNameResumePost(vmId, providerOptions(providerId, ads)),
    200,
  );
export const vmDestroy = (providerId: string, vmId: string, ads: AdsConfig) =>
  unwrapAs<null>(
    deleteVmApiV1VmsRequestorNameDelete(vmId, providerOptions(providerId, ads)),
    200,
  );

export function vmResize(
  providerId: string,
  vmId: string,
  resources: VMResources,
  ads: AdsConfig,
) {
  const payload: ResizeVMRequest = { resources };
  return unwrapAs<VMInfo>(
    resizeVmApiV1VmsRequestorNameResizePost(
      vmId,
      payload,
      providerOptions(providerId, ads),
    ),
    200,
  );
}

export const listSnapshots = (providerId: string, vmId: string, ads: AdsConfig) =>
  unwrapAs<VMSnapshot[]>(
    listSnapshotsApiV1VmsRequestorNameSnapshotsGet(
      vmId,
      providerOptions(providerId, ads),
    ),
    200,
  );

export const createSnapshot = (
  providerId: string,
  vmId: string,
  payload: CreateSnapshotRequest,
  ads: AdsConfig,
) =>
  unwrapAs<VMSnapshot>(
    createSnapshotApiV1VmsRequestorNameSnapshotsPost(
      vmId,
      payload,
      providerOptions(providerId, ads),
    ),
    200,
  );

export const restoreSnapshot = (
  providerId: string,
  vmId: string,
  snapshot: string,
  ads: AdsConfig,
) =>
  unwrapAs<VMInfo>(
    restoreSnapshotApiV1VmsRequestorNameSnapshotsSnapshotNameRestorePost(
      vmId,
      snapshot,
      providerOptions(providerId, ads),
    ),
    200,
  );

export const deleteSnapshot = (
  providerId: string,
  vmId: string,
  snapshot: string,
  ads: AdsConfig,
) =>
  unwrapAs<null>(
    deleteSnapshotApiV1VmsRequestorNameSnapshotsSnapshotNameDelete(
      vmId,
      snapshot,
      providerOptions(providerId, ads),
    ),
    200,
  );

type ApiResponse<TData, TStatus extends number = number> = {
  data: TData;
  status: TStatus;
  headers: Headers;
};

async function unwrapAs<TData, TResponse extends ApiResponse<unknown> = ApiResponse<unknown>>(
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
  const error = new Error(message || `HTTP ${status}`) as Error & { status: number };
  error.status = status;
  return error;
}

function centralDiscoveryOrigin(ads: AdsConfig): string {
  return ads.discovery_url.replace(/\/api\/v1\/?$/, "").replace(/\/$/, "");
}

function providerOptions(providerId: string, ads: AdsConfig): RequestInit {
  const headers = new Headers();
  headers.set("X-Proxy-Source", ads.mode || "arkiv");
  headers.set("X-Proxy-Token", process.env.NEXT_PUBLIC_PORT_CHECKER_TOKEN || "");
  if (ads.arkiv_rpc_url) headers.set("X-Proxy-Arkiv-Rpc", ads.arkiv_rpc_url);
  if (ads.arkiv_ws_url) headers.set("X-Proxy-Arkiv-Ws", ads.arkiv_ws_url);

  return withBaseUrl(proxyProviderOrigin(providerId), { headers });
}

function proxyProviderOrigin(providerId: string): string {
  const base = (process.env.NEXT_PUBLIC_PORT_CHECKER_URL || "http://localhost:9000")
    .replace(/\/$/, "");
  return `${base}/proxy/provider/${encodeURIComponent(providerId)}`;
}

async function providerFetch<TData>(
  providerId: string,
  path: string,
  ads: AdsConfig,
): Promise<TData> {
  const headers = new Headers();
  headers.set("X-Proxy-Source", ads.mode || "arkiv");
  headers.set("X-Proxy-Token", process.env.NEXT_PUBLIC_PORT_CHECKER_TOKEN || "");
  if (ads.arkiv_rpc_url) headers.set("X-Proxy-Arkiv-Rpc", ads.arkiv_rpc_url);
  if (ads.arkiv_ws_url) headers.set("X-Proxy-Arkiv-Ws", ads.arkiv_ws_url);
  const response = await fetch(`${proxyProviderOrigin(providerId)}${path}`, {
    headers,
    cache: "no-store",
  });
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw apiError(response.status, data);
  }
  return data as TData;
}

function withBaseUrl(baseUrl: string, init: RequestInit = {}): RequestInit {
  return { ...init, baseUrl } as RequestInit;
}
