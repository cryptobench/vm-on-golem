import React from "react";
import { listen } from "@tauri-apps/api/event";
import { providerApi } from "./providerApi";
import type {
  ActiveAlert,
  AlertRule,
  HistoryRange,
  MetricsHistoryResponse,
  MetricsLatestResponse,
  MonitoringOverview,
  ProviderInfo,
  ProviderServiceStatus,
  ProviderSummary,
  StartupSetupStatus,
  StreamStatus,
  VMAccessInfo,
  VMInfo,
  WebhookConfig,
} from "./types";

type LoadResult<T> = { value: T | null; error: string | null };

async function capture<T>(loader: () => Promise<T>): Promise<LoadResult<T>> {
  try {
    return { value: await loader(), error: null };
  } catch (err) {
    return { value: null, error: err instanceof Error ? err.message : String(err) };
  }
}

export type DashboardData = {
  info: ProviderInfo | null;
  summary: ProviderSummary | null;
  vms: VMInfo[];
  streams: StreamStatus[];
  monitoring: MonitoringOverview | null;
  latestMetrics: MetricsLatestResponse | null;
  hostCpuHistory: MetricsHistoryResponse | null;
  hostMemoryHistory: MetricsHistoryResponse | null;
  alerts: ActiveAlert[];
  alertRules: AlertRule[];
  webhooks: WebhookConfig[];
  errors: Record<string, string>;
};

export function useProviderServiceStatus() {
  const [status, setStatus] = React.useState<ProviderServiceStatus | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [busyAction, setBusyAction] = React.useState<"start" | "stop" | null>(null);
  const [setupStatus, setSetupStatus] = React.useState<StartupSetupStatus | null>(null);

  const refresh = React.useCallback(async () => {
    try {
      setError(null);
      setStatus(await providerApi.getServiceStatus());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  React.useEffect(() => {
    void refresh();
    const id = window.setInterval(() => void refresh(), 5000);
    return () => window.clearInterval(id);
  }, [refresh]);

  React.useEffect(() => {
    let active = true;
    const unsubscribe = listen<StartupSetupStatus>(
      "provider://setup-status",
      (event) => {
        if (active && isSetupStatus(event.payload)) {
          setSetupStatus(event.payload);
        }
      },
    );
    return () => {
      active = false;
      void unsubscribe.then((stop) => stop());
    };
  }, []);

  const runAction = React.useCallback(
    async (action: "start" | "stop") => {
      setBusyAction(action);
      setError(null);
      try {
        if (action === "start") {
          setSetupStatus(startingSetupStatus());
          await providerApi.startProvider();
        } else {
          await providerApi.stopProvider();
          setSetupStatus(null);
        }
        await refresh();
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        const parsed = parseSetupStatus(message);
        if (parsed) {
          setSetupStatus(parsed);
          setError(
            humanProviderStartError(
              parsed.error || parsed.message || "Secure connection setup failed",
            ),
          );
        } else {
          const friendly = humanProviderStartError(message);
          setError(friendly);
          setSetupStatus((current) =>
            current ? markSetupFailed(current, friendly) : current,
          );
        }
      } finally {
        setBusyAction(null);
      }
    },
    [refresh],
  );

  return { status, error, busyAction, setupStatus, refresh, runAction };
}

function startingSetupStatus(): StartupSetupStatus {
  return {
    message: "Preparing secure connection before the provider starts.",
    api_http_public_port: 80,
    api_https_public_port: 443,
    vm_port_range_start: 50800,
    vm_port_range_end: 50900,
    stages: [
      {
        name: "host_requirements",
        state: "running",
        label: "Checking host requirements",
        detail: "starting Multipass checks",
      },
      { name: "public_ip", state: "pending", label: "Public IP detected", detail: "" },
      { name: "network_access", state: "pending", label: "Ports 80 and 443 available", detail: "" },
      { name: "certificate", state: "pending", label: "Checking certificate", detail: "" },
      { name: "https_verification", state: "pending", label: "Secure endpoint verified", detail: "" },
      { name: "vm_port_range", state: "pending", label: "VM ports 50800-50900 reachable", detail: "" },
      { name: "provider_start", state: "pending", label: "Provider service started", detail: "" },
    ],
  };
}

function parseSetupStatus(message: string): StartupSetupStatus | null {
  try {
    const parsed = JSON.parse(message) as StartupSetupStatus;
    return Array.isArray(parsed.stages) ? parsed : null;
  } catch {
    return null;
  }
}

function isSetupStatus(value: unknown): value is StartupSetupStatus {
  return (
    typeof value === "object" &&
    value !== null &&
    Array.isArray((value as StartupSetupStatus).stages)
  );
}

function markSetupFailed(
  status: StartupSetupStatus,
  message: string,
): StartupSetupStatus {
  return {
    ...status,
    message,
    stages: status.stages.map((stage) =>
      stage.state === "running"
        ? {
            ...stage,
            state: "failed",
            detail: "not started",
            remediation: message,
          }
        : stage,
    ),
  };
}

function humanProviderStartError(message: string): string {
  const cleaned = stripAnsi(message).replace(/\s+/g, " ").trim();
  if (cleaned.includes("No module named 'dependency_injector.errors'")) {
    return (
      "The bundled provider sidecar is missing a packaged dependency. Rebuild "
      + "the provider sidecar, then restart the desktop app."
    );
  }
  if (cleaned.includes("PYI-272:ERROR") || cleaned.includes("Traceback")) {
    return "The bundled provider sidecar crashed before secure setup could start.";
  }
  return cleaned || "Provider command failed";
}

function stripAnsi(value: string): string {
  return value.replace(/\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])/g, "");
}

export function useDashboardData(serviceRunning: boolean | undefined) {
  const [data, setData] = React.useState<DashboardData | null>(null);
  const [loading, setLoading] = React.useState(false);
  const socketRef = React.useRef<WebSocket | null>(null);

  const refresh = React.useCallback(async () => {
    if (!serviceRunning) {
      setData(null);
      setLoading(false);
      return;
    }
    const socket = socketRef.current;
    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: "refresh" }));
      return;
    }
    setLoading(true);
    setData(await loadDashboardSnapshot());
    setLoading(false);
  }, [serviceRunning]);

  React.useEffect(() => {
    if (!serviceRunning) {
      socketRef.current?.close();
      socketRef.current = null;
      setData(null);
      setLoading(false);
      return;
    }
    let cancelled = false;
    let retryTimer: number | null = null;
    let retryDelay = 1000;

    const connect = async () => {
      setLoading((current) => current || data == null);
      try {
        const socket = new WebSocket(await providerApi.providerLiveUrl());
        socketRef.current = socket;
        socket.onopen = () => {
          retryDelay = 1000;
        };
        socket.onmessage = (message) => {
          const event = JSON.parse(String(message.data)) as ProviderLiveEvent;
          if (event.type === "snapshot" && event.data) {
            setData(normalizeDashboardData(event.data));
            setLoading(false);
          } else if (event.type === "update" && event.data) {
            setData((current) =>
              mergeDashboardPatch(current, event.data as Partial<DashboardData>),
            );
            setLoading(false);
          } else if (event.type === "error") {
            setData((current) =>
              mergeDashboardPatch(current, {
                errors: {
                  ...(current?.errors ?? {}),
                  [event.scope || "providerLive"]:
                    event.error || "Provider live stream error",
                },
              }),
            );
            setLoading(false);
          }
        };
        socket.onerror = () => {
          setData((current) =>
            mergeDashboardPatch(current, {
              errors: {
                ...(current?.errors ?? {}),
                providerLive: "Provider live stream unavailable",
              },
            }),
          );
        };
        socket.onclose = () => {
          if (socketRef.current === socket) socketRef.current = null;
          if (cancelled) return;
          retryTimer = window.setTimeout(connect, retryDelay);
          retryDelay = Math.min(retryDelay * 2, 10000);
        };
      } catch (error) {
        if (cancelled) return;
        setData((current) =>
          mergeDashboardPatch(current, {
            errors: {
              ...(current?.errors ?? {}),
              providerLive: error instanceof Error ? error.message : String(error),
            },
          }),
        );
        retryTimer = window.setTimeout(connect, retryDelay);
        retryDelay = Math.min(retryDelay * 2, 10000);
      }
    };

    void connect();
    return () => {
      cancelled = true;
      if (retryTimer != null) window.clearTimeout(retryTimer);
      socketRef.current?.close();
      socketRef.current = null;
    };
  }, [serviceRunning]);

  return { data, loading, refresh };
}

type ProviderLiveEvent = {
  type: "hello" | "snapshot" | "update" | "error" | "heartbeat";
  scope?: string | null;
  data?: Partial<DashboardData> | null;
  error?: string | null;
};

async function loadDashboardSnapshot(): Promise<DashboardData> {
  const [
    info,
    summary,
    vms,
    streams,
    monitoring,
    latestMetrics,
    hostCpuHistory,
    hostMemoryHistory,
    alerts,
    alertRules,
    webhooks,
  ] = await Promise.all([
    capture(providerApi.info),
    capture(providerApi.summary),
    capture(providerApi.vms),
    capture(providerApi.streams),
    capture(providerApi.monitoringOverview),
    capture(providerApi.metricsLatest),
    capture(() => providerApi.metricsHistory("1h")),
    capture(() => providerApi.metricsHistory("1h")),
    capture(providerApi.alerts),
    capture(providerApi.alertRules),
    capture(providerApi.webhooks),
  ]);

  const errors = Object.fromEntries(
    Object.entries({
      info: info.error,
      summary: summary.error,
      vms: vms.error,
      streams: streams.error,
      monitoring: monitoring.error,
      latestMetrics: latestMetrics.error,
      hostCpuHistory: hostCpuHistory.error,
      hostMemoryHistory: hostMemoryHistory.error,
      alerts: alerts.error,
      alertRules: alertRules.error,
      webhooks: webhooks.error,
    }).filter(([, error]) => error != null),
  ) as Record<string, string>;

  return {
    info: info.value,
    summary: summary.value,
    vms: vms.value ?? [],
    streams: streams.value ?? [],
    monitoring: monitoring.value,
    latestMetrics: latestMetrics.value,
    hostCpuHistory: hostCpuHistory.value,
    hostMemoryHistory: hostMemoryHistory.value,
    alerts: alerts.value ?? monitoring.value?.active_alerts ?? [],
    alertRules: alertRules.value ?? [],
    webhooks: webhooks.value ?? [],
    errors,
  };
}

function normalizeDashboardData(patch: Partial<DashboardData>): DashboardData {
  return mergeDashboardPatch(null, patch);
}

export function mergeDashboardPatch(
  current: DashboardData | null,
  patch: Partial<DashboardData>,
): DashboardData {
  return {
    info: patch.info ?? current?.info ?? null,
    summary: patch.summary ?? current?.summary ?? null,
    vms: patch.vms ?? current?.vms ?? [],
    streams: patch.streams ?? current?.streams ?? [],
    monitoring: patch.monitoring ?? current?.monitoring ?? null,
    latestMetrics: patch.latestMetrics ?? current?.latestMetrics ?? null,
    hostCpuHistory: patch.hostCpuHistory ?? current?.hostCpuHistory ?? null,
    hostMemoryHistory:
      patch.hostMemoryHistory ?? current?.hostMemoryHistory ?? null,
    alerts:
      patch.alerts ??
      current?.alerts ??
      patch.monitoring?.active_alerts ??
      current?.monitoring?.active_alerts ??
      [],
    alertRules: patch.alertRules ?? current?.alertRules ?? [],
    webhooks: patch.webhooks ?? current?.webhooks ?? [],
    errors: patch.errors ?? current?.errors ?? {},
  };
}

export type VmDetailData = {
  vm: VMInfo | null;
  access: VMAccessInfo | null;
  stream: StreamStatus | null;
  latest: MetricsLatestResponse | null;
  history: MetricsHistoryResponse | null;
  errors: Record<string, string>;
};

export function useVmDetail(vmId: string | null, range: HistoryRange) {
  const [data, setData] = React.useState<VmDetailData | null>(null);
  const [loading, setLoading] = React.useState(false);

  const refresh = React.useCallback(async () => {
    if (!vmId) {
      setData(null);
      return;
    }
    setLoading(true);
    const [vm, access, stream, latest, history] = await Promise.all([
      capture(() => providerApi.vm(vmId)),
      capture(() => providerApi.vmAccess(vmId)),
      capture(() => providerApi.vmStream(vmId)),
      capture(() => providerApi.vmMetricsLatest(vmId)),
      capture(() => providerApi.vmMetricsHistory(vmId, range)),
    ]);
    const errors = Object.fromEntries(
      Object.entries({
        vm: vm.error,
        access: access.error,
        stream: stream.error,
        latest: latest.error,
        history: history.error,
      }).filter(([, error]) => error != null),
    ) as Record<string, string>;
    setData({
      vm: vm.value,
      access: access.value,
      stream: stream.value,
      latest: latest.value,
      history: history.value,
      errors,
    });
    setLoading(false);
  }, [range, vmId]);

  React.useEffect(() => {
    void refresh();
  }, [refresh]);

  return { data, loading, refresh };
}
