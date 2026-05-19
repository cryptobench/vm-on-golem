import type { Rental, VMResources } from "./api";
import { sshEndpointLabel } from "./providerConnection";
import {
  deriveVmDisplayLifecycle,
  type LifecycleSource,
  type VmLifecycleView,
} from "./vmLifecycle";

export type VmSafeStatus =
  | {
      exists: true;
      data: Record<string, unknown>;
    }
  | {
      exists: false;
      code: number;
      error: string;
    };

export type RequestorVmProbe = {
  provider: Record<string, unknown> | null;
  providerError: unknown;
  safeStatus: VmSafeStatus | null;
  access: Record<string, unknown> | null;
  accessError: unknown;
  stream: Record<string, unknown> | null;
  streamError: unknown;
};

export type RequestorVmModel = {
  rental: Rental;
  hasLiveProbe: boolean;
  probePending: boolean;
  lifecycle: VmLifecycleView;
  provider: Record<string, unknown> | null;
  statusPayload: Record<string, unknown> | null;
  access: Record<string, unknown> | null;
  stream: Record<string, unknown> | null;
  resources: VMResources | undefined;
  platform: string;
  country: string;
  sshEndpoint: string;
  remainingSeconds: number | null;
  paymentState: string;
};

export function buildRequestorVmModel(
  rental: Rental,
  probe: RequestorVmProbe | null | undefined,
  options: { probePending?: boolean } = {},
): RequestorVmModel {
  const storedStatus = String(rental.status || "").toLowerCase();
  const storedTerminal = isTerminalVmStatus(storedStatus);
  const safeStatus = probe?.safeStatus || null;
  const statusPayload = safeStatus?.exists ? safeStatus.data : null;
  const access = probe?.access || null;
  const provider = probe?.provider || null;
  const paymentState = paymentStateFor(probe?.stream);
  const lifecycleSource = lifecycleSourceFor({
    access,
    paymentState,
    statusPayload,
    storedStatus,
    storedTerminal,
  });
  const lifecycle = storedTerminal
    ? deriveVmDisplayLifecycle({
        lifecycle: {
          status: storedStatus || "terminated",
          status_message: rental.status_message,
        },
      })
    : deriveVmDisplayLifecycle({
        lifecycle: lifecycleSource,
        fallback: {
          status: rental.status || (rental.ssh_port ? "running" : "creating"),
          lifecycle_stage: rental.lifecycle_stage,
          status_message: rental.status_message,
          progress: rental.progress,
          transitioning: rental.transitioning,
          next_poll_seconds: rental.next_poll_seconds,
        },
        safeStatus,
        statusError: safeStatus?.exists === false ? safeStatus : null,
        accessError: probe?.accessError || null,
      });
  const resources =
    ((statusPayload?.resources as VMResources | undefined) ||
      rental.resources) ??
    undefined;
  const platform =
    stringValue(provider?.platform) ||
    stringValue(statusPayload?.platform) ||
    rental.platform ||
    "Linux";

  return {
    rental,
    hasLiveProbe: !!probe,
    probePending: !!options.probePending,
    lifecycle,
    provider,
    statusPayload,
    access,
    stream: probe?.stream || null,
    resources,
    platform,
    country: stringValue(provider?.country),
    sshEndpoint: sshEndpointLabel({
      access: access as {
        ssh_host?: string | null;
        ssh_port?: number | string | null;
      } | null,
      provider: provider as {
        ip_address?: string | null;
        endpoint_url?: string | null;
      } | null,
      rental,
    }),
    remainingSeconds: remainingSeconds(probe?.stream),
    paymentState,
  };
}

export function isTerminalVmStatus(status?: string | null) {
  const normalized = String(status || "").toLowerCase();
  return (
    normalized === "terminated" ||
    normalized === "deleted" ||
    normalized === "payment_expired"
  );
}

function lifecycleSourceFor({
  access,
  paymentState,
  statusPayload,
  storedStatus,
  storedTerminal,
}: {
  access: Record<string, unknown> | null;
  paymentState: string;
  statusPayload: Record<string, unknown> | null;
  storedStatus: string;
  storedTerminal: boolean;
}): LifecycleSource | null {
  if (storedTerminal) return { status: storedStatus || "terminated" };
  if (paymentState === "expired") {
    return {
      status: "payment_expired",
      lifecycle_stage: "payment_expired",
      status_message: "Payment expired",
      transitioning: false,
    };
  }
  if (paymentState === "grace") {
    return {
      status: "payment_grace",
      lifecycle_stage: "payment_grace",
      status_message: "Payment grace period",
      transitioning: false,
    };
  }
  if (statusPayload?.status) return statusPayload as LifecycleSource;
  if (access?.status) return access as LifecycleSource;
  return null;
}

function paymentStateFor(stream?: Record<string, unknown> | null) {
  const state = stringValue(stream?.payment_state).toLowerCase();
  if (state) return state;
  const remaining = remainingSeconds(stream);
  return remaining === 0 ? "expired" : "";
}

function remainingSeconds(stream?: Record<string, unknown> | null) {
  const computed = stream?.computed as
    | { remaining_seconds?: number | null }
    | undefined;
  const value = computed?.remaining_seconds;
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function stringValue(value: unknown) {
  return typeof value === "string" ? value : "";
}
