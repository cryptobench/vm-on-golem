"use client";
import React from "react";
import useSWR from "swr";
import { loadRentals, saveRentals, vmStatusSafe } from "../lib/api";
import { useAds } from "../context/AdsContext";

export function useProjectRentals(projectId: string) {
  const { ads } = useAds();

  const adsKey = React.useMemo(() => {
    const mode = ads?.mode || "";
    const rpc = ads?.golem_base_rpc_url || "";
    const ws = ads?.golem_base_ws_url || "";
    const chain = ads?.chain_id || "";
    return `${mode}|${rpc}|${ws}|${chain}`;
  }, [ads]);

  const { data, mutate } = useSWR(
    ["project-rentals", projectId, adsKey],
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
        try {
          const st = await vmStatusSafe(r.provider_id, r.vm_id, ads);
          if (!st.exists && st.code === 404) {
            const createdAt = Number(r.created_at || 0);
            const isCreating = status === "creating";
            const withinGrace = isCreating && createdAt && nowSec - createdAt < 180; // 3 minutes
            if (!withinGrace && r.status !== "terminated") {
              next[i] = { ...r, status: "terminated", ssh_port: null, ended_at: nowSec };
              changed = true;
            }
          }
        } catch {}
      }
      if (changed) saveRentals(next as any);
      return next as any[];
    },
    {
      refreshInterval: 8000,
      revalidateOnMount: true,
      fallbackData: loadRentals(),
    }
  );

  const items = (data as any[]) || [];

  // setItems persists and updates the SWR cache
  const setItems = React.useCallback((next: any[]) => {
    saveRentals(next as any);
    mutate(next, { revalidate: false });
  }, [mutate]);

  // refresh triggers immediate revalidation
  const refresh = React.useCallback(() => { mutate(); }, [mutate]);

  return { items, setItems, refresh } as const;
}
