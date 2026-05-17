"use client";

import React from "react";
import { useAds } from "../context/AdsContext";
import {
  applyDiscoveryEvent,
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

    const socket = new WebSocket(ads.discovery_ws_url);
    let closedByEffect = false;

    socket.addEventListener("open", () => {
      socket.send(JSON.stringify(subscribeMessage(parsedFilters)));
    });

    socket.addEventListener("message", (message) => {
      try {
        const event = JSON.parse(String(message.data)) as DiscoveryEvent;
        if (event.type === "hello" || event.type === "heartbeat") return;
        if (event.type === "error") {
          setError(event.error || "Discovery websocket error");
          setLoading(false);
          return;
        }
        setRows((current) => applyDiscoveryEvent(current, event));
        if (event.type === "snapshot") setLoading(false);
      } catch (errorEvent) {
        setError(
          errorEvent instanceof Error ? errorEvent.message : String(errorEvent),
        );
        setLoading(false);
      }
    });

    socket.addEventListener("error", () => {
      setError("Discovery websocket connection failed");
      setLoading(false);
    });

    socket.addEventListener("close", () => {
      if (!closedByEffect) {
        setError("Discovery websocket closed");
        setLoading(false);
      }
    });

    return () => {
      closedByEffect = true;
      socket.close();
    };
  }, [ads.discovery_ws_url, enabled, filterKey]);

  return { rows, loading, error };
}
