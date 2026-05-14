import React from "react";
import { invoke } from "@tauri-apps/api/core";
import type {
  HistoryRange,
  MetricSample,
  MetricsHistoryResponse,
  MetricsLatestResponse,
} from "../../lib/types";

type ConnectionState = "idle" | "connecting" | "connected" | "degraded";

type HostMetricsLivePayload = {
  latest?: MetricsLatestResponse | null;
  history?: MetricsHistoryResponse | null;
  metrics_latest?: MetricsLatestResponse | null;
  metrics_history?: MetricsHistoryResponse | null;
  samples?: MetricSample[];
  status?: string | null;
  last_sample_at?: string | null;
  errors?: Record<string, string>;
};

type HostMetricsLiveEvent = {
  type: "hello" | "snapshot" | "update" | "error" | "heartbeat";
  generated_at: string;
  scope?: string | null;
  data?: HostMetricsLivePayload | null;
  error?: string | null;
};

type HostMonitoringLiveState = {
  connection: ConnectionState;
  metricsLatest: MetricsLatestResponse | null;
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
  | { type: "snapshot"; data: HostMetricsLivePayload }
  | { type: "update"; data: HostMetricsLivePayload }
  | { type: "error"; error: string };

const initialState: HostMonitoringLiveState = {
  connection: "idle",
  metricsLatest: null,
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
    return mergePayload(state, action.data, true);
  }
  if (action.type === "update") {
    return mergePayload(state, action.data, false);
  }
  return state;
}

export function useHostMonitoringLive(range: HistoryRange) {
  const [state, dispatch] = React.useReducer(hostLiveReducer, initialState);
  const socketRef = React.useRef<WebSocket | null>(null);

  React.useEffect(() => {
    if (typeof window === "undefined") return;
    let cancelled = false;
    let socket: WebSocket | null = null;
    dispatch({ type: "connecting" });

    hostMetricsLiveUrl(range)
      .then((url) => {
        if (cancelled) return;
        socket = new WebSocket(url);
        socketRef.current = socket;
        socket.onopen = () => dispatch({ type: "connected" });
        socket.onmessage = (message) => {
          try {
            const event = JSON.parse(String(message.data)) as HostMetricsLiveEvent;
            if (event.type === "snapshot" && event.data) {
              dispatch({ type: "snapshot", data: event.data });
            } else if (
              event.type === "update" &&
              event.scope === "metrics" &&
              event.data
            ) {
              dispatch({ type: "update", data: event.data });
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
  }, [range]);

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
  };
}

async function hostMetricsLiveUrl(range: HistoryRange) {
  const baseUrl = await invoke<string>("provider_api_base_url");
  const url = new URL(`${baseUrl}/monitoring/host/live`);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.searchParams.set("history_range", range);
  return url.toString();
}

function mergePayload(
  state: HostMonitoringLiveState,
  payload: HostMetricsLivePayload,
  replaceHistory: boolean,
): HostMonitoringLiveState {
  const latest = payload.metrics_latest ?? payload.latest ?? state.metricsLatest;
  const history = payload.metrics_history ?? payload.history;
  const samples = Array.isArray(payload.samples) ? payload.samples : [];
  return {
    ...state,
    metricsLatest: latest ?? null,
    metricsHistory:
      history ??
      (replaceHistory
        ? state.metricsHistory
        : mergeMetricSamples(state.metricsHistory, samples)),
    status: payload.status ?? state.status,
    lastSampleAt: payload.last_sample_at ?? state.lastSampleAt,
    lastEventAt: Date.now(),
    errors: payload.errors ?? state.errors,
  };
}

function mergeMetricSamples(
  history: MetricsHistoryResponse | null,
  samples: MetricSample[],
): MetricsHistoryResponse | null {
  if (!samples.length) return history;
  const byKey = new Map<string, MetricSample>();
  [...(history?.samples ?? []), ...samples].forEach((sample) => {
    byKey.set(metricSampleKey(sample), sample);
  });
  return {
    samples: Array.from(byKey.values())
      .sort(
        (a, b) =>
          a.timestamp.localeCompare(b.timestamp) ||
          a.metric.localeCompare(b.metric),
      )
      .slice(-10_000),
  };
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
