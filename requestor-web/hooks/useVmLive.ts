"use client";

import React from "react";
import {
  vmLiveUrl,
  type VmLiveEvent,
  type VmLiveSnapshot,
  type VmMonitoringHistory,
  type VmMonitoringLatest,
} from "../lib/api";
import { getProviderVmSession } from "../lib/providerSession";

type ConnectionState = "idle" | "connecting" | "connected" | "degraded";

export type VmLiveState = {
  connection: ConnectionState;
  providerInfo: Record<string, unknown> | null;
  lifecycle: Record<string, unknown> | null;
  access: Record<string, unknown> | null;
  job: Record<string, unknown> | null;
  snapshots: Array<Record<string, unknown>> | null;
  stream: Record<string, unknown> | null;
  metricsLatest: VmMonitoringLatest | null;
  metricsHistory: VmMonitoringHistory | null;
  errors: Record<string, string>;
};

type Action =
  | { type: "connecting" }
  | { type: "connected" }
  | { type: "degraded"; error?: string }
  | { type: "snapshot"; data: VmLiveSnapshot }
  | { type: "update"; scope: string; data: unknown }
  | { type: "error"; scope?: string | null; error: string };

const initialState: VmLiveState = {
  connection: "idle",
  providerInfo: null,
  lifecycle: null,
  access: null,
  job: null,
  snapshots: null,
  stream: null,
  metricsLatest: null,
  metricsHistory: null,
  errors: {},
};

export function vmLiveReducer(
  state: VmLiveState,
  action: Action,
): VmLiveState {
  if (action.type === "connecting") {
    return { ...initialState, connection: "connecting" };
  }
  if (action.type === "connected") return { ...state, connection: "connected" };
  if (action.type === "degraded") {
    return {
      ...state,
      connection: "degraded",
      errors: action.error
        ? { ...state.errors, connection: action.error }
        : state.errors,
    };
  }
  if (action.type === "error") {
    return {
      ...state,
      errors: {
        ...state.errors,
        [action.scope || "connection"]: action.error,
      },
    };
  }
  if (action.type === "snapshot") {
    return {
      ...state,
      providerInfo: action.data.provider_info || null,
      lifecycle: action.data.lifecycle || null,
      access: action.data.access || null,
      job: action.data.job || null,
      snapshots: action.data.snapshots || null,
      stream: action.data.stream || null,
      metricsLatest: action.data.metrics_latest || null,
      metricsHistory: action.data.metrics_history || null,
      errors: action.data.errors || {},
    };
  }
  if (action.type === "update") {
    if (action.scope === "provider_info") {
      return { ...state, providerInfo: asRecord(action.data) };
    }
    if (action.scope === "lifecycle") {
      return { ...state, lifecycle: asRecord(action.data) };
    }
    if (action.scope === "access") {
      return { ...state, access: asRecord(action.data) };
    }
    if (action.scope === "job") {
      return { ...state, job: asRecord(action.data) };
    }
    if (action.scope === "snapshots") {
      return {
        ...state,
        snapshots: Array.isArray(action.data)
          ? (action.data as Array<Record<string, unknown>>)
          : [],
      };
    }
    if (action.scope === "stream") {
      return { ...state, stream: asRecord(action.data) };
    }
    if (action.scope === "metrics") {
      const data = asRecord(action.data);
      const history = data?.history as VmMonitoringHistory | undefined;
      const samples = Array.isArray(data?.samples)
        ? (data.samples as VmMonitoringHistory["samples"])
        : [];
      return {
        ...state,
        metricsLatest:
          (data?.latest as VmMonitoringLatest | undefined) || state.metricsLatest,
        metricsHistory: history || mergeMetricSamples(state.metricsHistory, samples),
      };
    }
  }
  return state;
}

export function useVmLive(
  providerEndpointUrl?: string | null,
  vmId?: string | null,
  jobId?: string | null,
  historyRange = "1h",
) {
  const [state, dispatch] = React.useReducer(vmLiveReducer, initialState);
  const socketRef = React.useRef<WebSocket | null>(null);

  React.useEffect(() => {
    if (!providerEndpointUrl || !vmId || typeof window === "undefined") return;
    const socket = new WebSocket(
      vmLiveUrl(providerEndpointUrl, vmId, { jobId, historyRange }),
    );
    socketRef.current = socket;
    dispatch({ type: "connecting" });

    socket.onopen = async () => {
      try {
        const token = await getProviderVmSession(providerEndpointUrl, vmId);
        if (socket.readyState !== WebSocket.OPEN) return;
        socket.send(JSON.stringify({ type: "auth", token }));
        dispatch({ type: "connected" });
      } catch (error) {
        dispatch({ type: "degraded", error: String(error) });
        socket.close();
      }
    };
    socket.onmessage = (message) => {
      try {
        const event = JSON.parse(String(message.data)) as VmLiveEvent;
        if (event.type === "snapshot") {
          dispatch({ type: "snapshot", data: event.data as VmLiveSnapshot });
        } else if (event.type === "update" && event.scope) {
          dispatch({ type: "update", scope: event.scope, data: event.data });
        } else if (event.type === "error") {
          dispatch({
            type: "error",
            scope: event.scope,
            error: event.error || "Live stream error",
          });
        }
      } catch (error) {
        dispatch({ type: "error", error: String(error) });
      }
    };
    socket.onerror = () => {
      dispatch({ type: "degraded", error: "Live stream unavailable" });
    };
    socket.onclose = () => {
      if (socketRef.current === socket) {
        dispatch({ type: "degraded" });
      }
    };

    return () => {
      socketRef.current = null;
      socket.close();
    };
  }, [providerEndpointUrl, vmId, jobId, historyRange]);

  const send = React.useCallback((payload: Record<string, unknown>) => {
    const socket = socketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) return false;
    socket.send(JSON.stringify(payload));
    return true;
  }, []);

  const refresh = React.useCallback(
    (scopes?: string[]) => send({ type: "refresh", scopes }),
    [send],
  );

  return {
    state,
    connected: state.connection === "connected",
    refresh,
    send,
  };
}

function asRecord(value: unknown) {
  return value && typeof value === "object"
    ? (value as Record<string, unknown>)
    : null;
}

function mergeMetricSamples(
  history: VmMonitoringHistory | null,
  samples: VmMonitoringHistory["samples"],
): VmMonitoringHistory | null {
  if (!samples.length) return history;

  const existing = history?.samples || [];
  const byKey = new Map<string, VmMonitoringHistory["samples"][number]>();
  [...existing, ...samples].forEach((sample) => {
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

function metricSampleKey(sample: VmMonitoringHistory["samples"][number]) {
  return [
    sample.scope,
    sample.source,
    sample.vm_id || "",
    sample.metric,
    sample.timestamp,
  ].join(":");
}
