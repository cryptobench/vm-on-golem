import React from "react";
import { invoke } from "@tauri-apps/api/core";
import type {
  HistoryRange,
  MetricHistoryPoint,
  MetricSample,
  MetricsHistoryResponse,
  MetricsLatestResponse,
} from "../../lib/types";
import { providerAdminToken } from "../../lib/providerApi";

type ConnectionState = "idle" | "connecting" | "connected" | "degraded";

type HostMetricsLivePayload = {
  latest?: MetricsLatestResponse | null;
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
  | { type: "history"; data: HostMetricsLivePayload }
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
  if (action.type === "history") {
    return mergeHistoryPayload(state, action.data);
  }
  if (action.type === "update") {
    return mergePayload(state, action.data, false);
  }
  return state;
}

export function useHostMonitoringLive() {
  const [state, dispatch] = React.useReducer(hostLiveReducer, initialState);
  const socketRef = React.useRef<WebSocket | null>(null);
  const historyRangeRef = React.useRef<HistoryRange>("1h");
  const historyRangeUpdatePendingRef = React.useRef(false);

  const setHistoryRange = React.useCallback((range: HistoryRange) => {
    if (historyRangeRef.current === range) return;
    historyRangeRef.current = range;
    const socket = socketRef.current;
    if (socket?.readyState === WebSocket.OPEN) {
      historyRangeUpdatePendingRef.current = true;
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
            historyRangeUpdatePendingRef.current = true;
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
              dispatch({ type: "snapshot", data: event.data });
            } else if (
              event.type === "update" &&
              event.scope === "metrics" &&
              event.data
            ) {
              if (historyRangeUpdatePendingRef.current && hasHistory(event.data)) {
                historyRangeUpdatePendingRef.current = false;
                dispatch({ type: "history", data: event.data });
              } else {
                dispatch({ type: "update", data: event.data });
              }
            } else if (event.type === "error") {
              historyRangeUpdatePendingRef.current = false;
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
  payload: HostMetricsLivePayload,
): HostMonitoringLiveState {
  return {
    ...state,
    metricsHistory: payload.metrics_history ?? state.metricsHistory,
    lastEventAt: Date.now(),
    errors: payload.errors ?? state.errors,
  };
}

function mergePayload(
  state: HostMonitoringLiveState,
  payload: HostMetricsLivePayload,
  replaceHistory: boolean,
): HostMonitoringLiveState {
  const latest = payload.metrics_latest ?? payload.latest ?? state.metricsLatest;
  const samples = Array.isArray(payload.samples) ? payload.samples : [];
  return {
    ...state,
    metricsLatest: latest ?? null,
    metricsHistory:
      payload.metrics_history ??
      (replaceHistory
        ? state.metricsHistory
        : mergeMetricSamples(state.metricsHistory, samples)),
    status: payload.status ?? state.status,
    lastSampleAt: payload.last_sample_at ?? state.lastSampleAt,
    lastEventAt: Date.now(),
    errors: payload.errors ?? state.errors,
  };
}

function hasHistory(payload: HostMetricsLivePayload) {
  return Boolean(payload.metrics_history);
}

function mergeMetricSamples(
  history: MetricsHistoryResponse | null,
  samples: MetricSample[],
): MetricsHistoryResponse | null {
  if (!samples.length || !history) return history;
  const byKey = new Map<string, MetricHistoryPoint>();
  history.points.forEach((point) => {
    byKey.set(metricPointKey(point), point);
  });
  samples.forEach((sample) => {
    const point = metricSamplePoint(sample, history.resolution_seconds);
    const existing = byKey.get(metricPointKey(point));
    byKey.set(
      metricPointKey(point),
      existing ? mergeMetricPoint(existing, sample.value) : point,
    );
  });
  return {
    ...history,
    points: Array.from(byKey.values())
      .sort(
        (a, b) =>
          a.bucket_start.localeCompare(b.bucket_start) ||
          a.metric.localeCompare(b.metric),
      )
      .slice(-10_000),
    generated_at: new Date().toISOString(),
  };
}

function metricSamplePoint(
  sample: MetricSample,
  resolutionSeconds: number,
): MetricHistoryPoint {
  const timestamp = Date.parse(sample.timestamp);
  if (!Number.isFinite(timestamp)) {
    throw new Error(`Metric timestamp must be absolute: ${sample.timestamp}`);
  }
  const bucketStartMs =
    Math.floor(timestamp / (resolutionSeconds * 1000)) *
    resolutionSeconds *
    1000;
  return {
    scope: sample.scope,
    source: sample.source,
    vm_id: sample.vm_id,
    metric: sample.metric,
    unit: sample.unit,
    bucket_start: new Date(bucketStartMs).toISOString(),
    bucket_end: new Date(bucketStartMs + resolutionSeconds * 1000).toISOString(),
    avg: sample.value,
    min: sample.value,
    max: sample.value,
    count: 1,
  };
}

function mergeMetricPoint(
  point: MetricHistoryPoint,
  sampleValue: number,
): MetricHistoryPoint {
  const count = point.count + 1;
  return {
    ...point,
    avg: (point.avg * point.count + sampleValue) / count,
    min: Math.min(point.min, sampleValue),
    max: Math.max(point.max, sampleValue),
    count,
  };
}

function metricPointKey(point: MetricHistoryPoint) {
  return [
    point.scope,
    point.source,
    point.vm_id || "",
    point.metric,
    point.unit,
    point.bucket_start,
  ].join(":");
}
