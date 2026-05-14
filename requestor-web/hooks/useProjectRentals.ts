"use client";
import React from "react";
import useSWR from "swr";
import { loadRentals, saveRentals, vmStatusSafe } from "../lib/api";

export function useProjectRentals(projectId: string) {
  const [validatedKey, setValidatedKey] = React.useState<string | null>(null);

  const rentalsKey = projectId;

  const { data, isValidating, mutate } = useSWR(
    ["project-rentals", projectId],
    async () => {
      const list = loadRentals();
      const next = [...list];
      let changed = false;
      const nowSec = Math.floor(Date.now() / 1000);
      for (let i = 0; i < next.length; i++) {
        const r: any = next[i];
        if ((r.project_id || "default") !== projectId) continue;
        const status = String(r.status || "").toLowerCase();
        if (status === "terminated" || status === "deleted") continue;
        if (!r.provider_endpoint_url) continue;
        const st = await vmStatusSafe(r.provider_endpoint_url, r.vm_id);
        if (!st.exists && st.code === 404) {
          const createdAt = Number(r.created_at || 0);
          const isCreating = status === "creating";
          const withinGrace = isCreating && createdAt && nowSec - createdAt < 180; // 3 minutes
          if (!withinGrace && r.status !== "terminated") {
            next[i] = {
              ...r,
              status: "terminated",
              ssh_port: null,
              ended_at: nowSec,
              terminated_at: nowSec,
              termination_reason: "provider_missing",
            };
            changed = true;
          }
        }
      }
      if (changed) saveRentals(next as any);
      return next as any[];
    },
    {
      refreshInterval: 8000,
      revalidateOnMount: true,
    }
  );

  const items = (data as any[]) || [];
  React.useEffect(() => {
    if (data !== undefined && !isValidating) setValidatedKey(rentalsKey);
  }, [data, isValidating, rentalsKey]);
  const isInitialLoading = validatedKey !== rentalsKey;

  // setItems persists and updates the SWR cache
  const setItems = React.useCallback((next: any[]) => {
    saveRentals(next as any);
    mutate(next, { revalidate: false });
  }, [mutate]);

  // refresh triggers immediate revalidation
  const refresh = React.useCallback(() => { mutate(); }, [mutate]);

  return { items, isInitialLoading, setItems, refresh } as const;
}
