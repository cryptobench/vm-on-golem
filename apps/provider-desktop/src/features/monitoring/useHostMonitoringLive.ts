import React from "react";
import { invoke } from "@tauri-apps/api/core";
import type {
  HistoryRange,
  MetricSample,
  MetricsHistoryResponse,
  MetricsLatestResponse,
} from "../../lib/types";
import { providerAdminToken } from "../../lib/providerApi";

type ConnectionState = "idle" | "connecting" | "connected" | "degraded";

type HostMetricsLivePayload = {
  latest?: MetricsLatestResponse | null;
  samples?: MetricSample[];
  status?: string | null;
  last_sample_at?: string | null;
  errors?: Record<string, string>;
};

type HostMetricsSnapshotPayload = {
  metrics_live?: HostMetricsLivePayload | null;
  metrics_history?: MetricsHistoryResponse | null;
  errors?: Record<string, string>;
};

type HostMetricsLiveEvent = {
  type: "hello" | "snapshot" | "update" | "error" | "heartbeat";
  generated_at: string;
  scope?: string | null;
  data?: unknown;
  error?: string | null;
};

type HostMonitoringLiveState = {
  connection: ConnectionState;
  metricsLatest: MetricsLatestResponse | null;
  metricsLiveSamples: MetricSample[];
  metricsHistory: MetricsHistoryResponse | null;
  status: string | null;
  lastSampleAt: string | null;
  lastEventAt: number | null;
  errors: Record<string, string>;
};

type Action =
  | { type: "connecting" }
  | { type: "connected" }
  | { type: "degraded"; error?: string }
  | { type: "snapshot"; data: HostMetricsSnapshotPayload }
  | { type: "metricsLive"; data: HostMetricsLivePayload }
  | { type: "metricsHistory"; data: MetricsHistoryResponse }
  | { type: "error"; error: string };

const initialState: HostMonitoringLiveState = {
  connection: "idle",
  metricsLatest: null,
  metricsLiveSamples: [],
  metricsHistory: null,
  status: null,
  lastSampleAt: null,
  lastEventAt: null,
  errors: {},
};

function hostLiveReducer(
  state: HostMonitoringLiveState,
  action: Action,
): HostMonitoringLiveState {
  if (action.type === "connecting") {
    return { ...initialState, connection: "connecting" };
  }
  if (action.type === "connected") return { ...state, connection: "connected" };
  if (action.type === "degraded") {
    return {
      ...state,
      connection: "degraded",
      errors: action.error
        ? { ...state.errors, hostLive: action.error }
        : state.errors,
    };
  }
  if (action.type === "error") {
    return {
      ...state,
      errors: { ...state.errors, hostLive: action.error },
    };
  }
  if (action.type === "snapshot") {
    return {
      ...mergeLivePayload(state, action.data.metrics_live ?? {}),
      metricsHistory: action.data.metrics_history ?? state.metricsHistory,
      errors: action.data.errors ?? state.errors,
    };
  }
  if (action.type === "metricsHistory") {
    return mergeHistoryPayload(state, action.data);
  }
  if (action.type === "metricsLive") {
    return mergeLivePayload(state, action.data);
  }
  return state;
}

export function useHostMonitoringLive() {
  const [state, dispatch] = React.useReducer(hostLiveReducer, initialState);
  const socketRef = React.useRef<WebSocket | null>(null);
  const historyRangeRef = React.useRef<HistoryRange>("1h");

  const setHistoryRange = React.useCallback((range: HistoryRange) => {
    if (historyRangeRef.current === range) return;
    historyRangeRef.current = range;
    const socket = socketRef.current;
    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: "set_history_range", history_range: range }));
    }
  }, []);

  React.useEffect(() => {
    if (typeof window === "undefined") return;
    let cancelled = false;
    let socket: WebSocket | null = null;
    dispatch({ type: "connecting" });

    Promise.all([hostMetricsLiveUrl(historyRangeRef.current), providerAdminToken()])
      .then(([url, token]) => {
        if (cancelled) return;
        socket = new WebSocket(url);
        socketRef.current = socket;
        socket.onopen = () => {
          socket?.send(JSON.stringify({ type: "auth", token }));
          if (historyRangeRef.current !== "1h") {
            socket?.send(
              JSON.stringify({
                type: "set_history_range",
                history_range: historyRangeRef.current,
              }),
            );
          }
          dispatch({ type: "connected" });
        };
        socket.onmessage = (message) => {
          try {
            const event = JSON.parse(String(message.data)) as HostMetricsLiveEvent;
            if (event.type === "snapshot" && event.data) {
              dispatch({
                type: "snapshot",
                data: event.data as HostMetricsSnapshotPayload,
              });
            } else if (
              event.type === "update" &&
              event.scope === "metrics_live" &&
              event.data
            ) {
              dispatch({
                type: "metricsLive",
                data: event.data as HostMetricsLivePayload,
              });
            } else if (
              event.type === "update" &&
              event.scope === "metrics_history" &&
              event.data
            ) {
              dispatch({
                type: "metricsHistory",
                data: event.data as MetricsHistoryResponse,
              });
            } else if (event.type === "error") {
              dispatch({ type: "error", error: event.error || "Live stream error" });
            }
          } catch (error) {
            dispatch({ type: "error", error: String(error) });
          }
        };
        socket.onerror = () => {
          dispatch({ type: "degraded", error: "Host live stream unavailable" });
        };
        socket.onclose = () => {
          if (socketRef.current === socket) {
            dispatch({ type: "degraded", error: "Host live stream disconnected" });
          }
        };
      })
      .catch((error) => {
        dispatch({
          type: "degraded",
          error: error instanceof Error ? error.message : String(error),
        });
      });

    return () => {
      cancelled = true;
      socketRef.current = null;
      socket?.close();
    };
  }, []);

  React.useEffect(() => {
    if (state.connection !== "connected" || typeof window === "undefined") return;
    const id = window.setInterval(() => {
      const lastEventAt = state.lastEventAt;
      if (lastEventAt && Date.now() - lastEventAt > 3500) {
        dispatch({
          type: "degraded",
          error: "Host live stream stopped sending metrics",
        });
        const socket = socketRef.current;
        socketRef.current = null;
        socket?.close();
      }
    }, 1000);
    return () => window.clearInterval(id);
  }, [state.connection, state.lastEventAt]);

  const error =
    state.errors.hostLive ??
    (state.connection === "connecting" ? "Connecting to host live stream" : null);

  return {
    state,
    connected: state.connection === "connected",
    error,
    setHistoryRange,
  };
}

async function hostMetricsLiveUrl(range: HistoryRange) {
  const baseUrl = await invoke<string>("provider_api_base_url");
  const url = new URL(`${baseUrl}/monitoring/host/live`);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.searchParams.set("history_range", range);
  return url.toString();
}

function mergeHistoryPayload(
  state: HostMonitoringLiveState,
  history: MetricsHistoryResponse,
): HostMonitoringLiveState {
  return {
    ...state,
    metricsHistory: history,
    lastEventAt: Date.now(),
  };
}

function mergeLivePayload(
  state: HostMonitoringLiveState,
  payload: HostMetricsLivePayload,
): HostMonitoringLiveState {
  const samples = Array.isArray(payload.samples) ? payload.samples : [];
  return {
    ...state,
    metricsLatest: payload.latest ?? state.metricsLatest,
    metricsLiveSamples: mergeMetricSamples(state.metricsLiveSamples, samples),
    status: payload.status ?? state.status,
    lastSampleAt: payload.last_sample_at ?? state.lastSampleAt,
    lastEventAt: Date.now(),
    errors: payload.errors ?? state.errors,
  };
}

function mergeMetricSamples(
  current: MetricSample[],
  samples: MetricSample[],
): MetricSample[] {
  if (!samples.length) return current;
  const byKey = new Map<string, MetricSample>();
  [...current, ...samples].forEach((sample) => {
    byKey.set(metricSampleKey(sample), sample);
  });
  return Array.from(byKey.values())
    .sort(
      (a, b) =>
        a.timestamp.localeCompare(b.timestamp) ||
        a.metric.localeCompare(b.metric),
    )
    .slice(-10_000);
}

function metricSampleKey(sample: MetricSample) {
  return [
    sample.scope,
    sample.source,
    sample.vm_id || "",
    sample.metric,
    sample.timestamp,
  ].join(":");
}
