"use client";

import React from "react";
import { useAds } from "../context/AdsContext";
import {
  applyDiscoveryEvent,
  DISCOVERY_RECONNECT_INITIAL_DELAY_MS,
  nextDiscoveryReconnectDelayMs,
  subscribeMessage,
  type DiscoveryEvent,
  type DiscoveryFilters,
} from "../lib/discovery";
import type { ProviderAd } from "../lib/api";

export function useDiscoveryProviders(
  filters: DiscoveryFilters,
  enabled = true,
) {
  const { ads } = useAds();
  const [rows, setRows] = React.useState<ProviderAd[]>([]);
  const [loading, setLoading] = React.useState(enabled);
  const [error, setError] = React.useState<string | null>(null);
  const filterKey = JSON.stringify(filters);

  React.useEffect(() => {
    const parsedFilters = JSON.parse(filterKey) as DiscoveryFilters;
    if (!enabled) {
      setRows([]);
      setLoading(false);
      setError(null);
      return;
    }

    setRows([]);
    setLoading(true);
    setError(null);

    let socket: WebSocket | null = null;
    let closedByEffect = false;
    let retryTimer: number | null = null;
    let retryDelayMs = DISCOVERY_RECONNECT_INITIAL_DELAY_MS;

    const scheduleReconnect = (message: string) => {
      if (closedByEffect || retryTimer != null) return;
      setError(message);
      setLoading(false);
      retryTimer = window.setTimeout(() => {
        retryTimer = null;
        connect();
      }, retryDelayMs);
      retryDelayMs = nextDiscoveryReconnectDelayMs(retryDelayMs);
    };

    const connect = () => {
      if (closedByEffect) return;
      socket = new WebSocket(ads.discovery_ws_url);
      const currentSocket = socket;

      currentSocket.addEventListener("open", () => {
        currentSocket.send(JSON.stringify(subscribeMessage(parsedFilters)));
      });

      currentSocket.addEventListener("message", (message) => {
        try {
          const event = JSON.parse(String(message.data)) as DiscoveryEvent;
          if (event.type === "hello" || event.type === "heartbeat") return;
          if (event.type === "error") {
            setError(event.error || "Discovery websocket error");
            setLoading(false);
            return;
          }
          setRows((current) => applyDiscoveryEvent(current, event));
          if (event.type === "snapshot") {
            retryDelayMs = DISCOVERY_RECONNECT_INITIAL_DELAY_MS;
            setError(null);
            setLoading(false);
          }
        } catch (errorEvent) {
          setError(
            errorEvent instanceof Error ? errorEvent.message : String(errorEvent),
          );
          setLoading(false);
        }
      });

      currentSocket.addEventListener("error", () => {
        scheduleReconnect("Discovery websocket connection failed");
      });

      currentSocket.addEventListener("close", () => {
        if (socket === currentSocket) socket = null;
        scheduleReconnect("Discovery websocket closed; reconnecting");
      });
    };

    connect();

    return () => {
      closedByEffect = true;
      if (retryTimer != null) window.clearTimeout(retryTimer);
      socket?.close();
      socket = null;
    };
  }, [ads.discovery_ws_url, enabled, filterKey]);

  return { rows, loading, error };
}
