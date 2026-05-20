"use client";
import React from "react";
import useSWR from "swr";
import { loadRentals, loadSettings, saveRentals } from "../lib/api";
import { usePaymentStreamsLive } from "../lib/paymentStreamLive";
import { reconcileTerminatedStreamRentals } from "../lib/rentalReconciliation";
import { getRequestorRuntimeConfig } from "../lib/runtimeConfig";

function resolveStreamPaymentAddress() {
  return (
    loadSettings().stream_payment_address ||
    getRequestorRuntimeConfig().streamPaymentAddress ||
    ""
  ).trim();
}

export function useRentals() {
  const [validatedKey, setValidatedKey] = React.useState<string | null>(null);
  const [streamPaymentAddress, setStreamPaymentAddress] = React.useState(
    resolveStreamPaymentAddress,
  );

  const rentalsKey = "rentals";

  const { data, isValidating, mutate } = useSWR(
    ["rentals"],
    async () => loadRentals(),
    {
      refreshInterval: 8000,
      revalidateOnMount: true,
    },
  );

  React.useEffect(() => {
    if (typeof window === "undefined") return;

    const syncSettings = () => {
      setStreamPaymentAddress(resolveStreamPaymentAddress());
    };

    window.addEventListener("requestor_settings_changed", syncSettings);
    window.addEventListener("storage", syncSettings);
    return () => {
      window.removeEventListener("requestor_settings_changed", syncSettings);
      window.removeEventListener("storage", syncSettings);
    };
  }, []);

  React.useEffect(() => {
    if (typeof window === "undefined") return;
    const syncRentals = (event?: Event) => {
      const detail = (event as CustomEvent | undefined)?.detail;
      mutate(Array.isArray(detail) ? detail : loadRentals(), {
        revalidate: false,
      });
    };
    window.addEventListener("requestor_rentals_changed", syncRentals);
    window.addEventListener("storage", syncRentals);
    return () => {
      window.removeEventListener("requestor_rentals_changed", syncRentals);
      window.removeEventListener("storage", syncRentals);
    };
  }, [mutate]);

  const items = (data as any[]) || [];
  const streamRentals = React.useMemo(
    () =>
      items.filter((r) => {
        const status = String(r.status || "").toLowerCase();
        return (
          status !== "terminated" &&
          status !== "deleted" &&
          r.stream_id != null &&
          r.stream_id !== ""
        );
      }),
    [items],
  );
  const liveStreams = usePaymentStreamsLive(
    streamPaymentAddress,
    streamRentals,
  );

  React.useEffect(() => {
    if (!streamPaymentAddress || !streamRentals.length) return;
    const result = reconcileTerminatedStreamRentals(items, liveStreams.entries);
    if (!result.changed) return;
    saveRentals(result.rentals as any);
    mutate(result.rentals, { revalidate: false });
  }, [
    items,
    liveStreams.entries,
    mutate,
    streamPaymentAddress,
    streamRentals.length,
  ]);

  React.useEffect(() => {
    if (data !== undefined && !isValidating) setValidatedKey(rentalsKey);
  }, [data, isValidating, rentalsKey]);
  const isInitialLoading = validatedKey !== rentalsKey;

  // setItems persists and updates the SWR cache
  const setItems = React.useCallback(
    (next: any[]) => {
      saveRentals(next as any);
      mutate(next, { revalidate: false });
    },
    [mutate],
  );

  // refresh triggers immediate revalidation
  const refresh = React.useCallback(() => {
    mutate();
  }, [mutate]);

  return { items, isInitialLoading, setItems, refresh } as const;
}
