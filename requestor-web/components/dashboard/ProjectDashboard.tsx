"use client";
import React from "react";
import { loadRentals, saveRentals, vmAccess, vmStatusSafe, type Rental, loadSettings } from "../../lib/api";
import { fetchStreamWithMeta } from "../../lib/streams";
import { useProjects } from "../../context/ProjectsContext";
import { useAds } from "../../context/AdsContext";
import { useToast } from "../ui/Toast";
import { StreamsMini } from "./StreamsMini";
import { buildSshCommand, copyText } from "../../lib/ssh";
import { VmCard } from "../vm/VmCard";

// Using shared VmCard component for consistency

export function ProjectDashboard() {
  const { activeId, projects } = useProjects();
  const { ads } = useAds();
  const { show } = useToast();
  const [items, setItems] = React.useState<Rental[]>([]);
  const [busyId, setBusyId] = React.useState<string | null>(null);

  React.useEffect(() => {
    const list = (loadRentals() || []).filter(r => (r.project_id || 'default') === activeId);
    setItems(list);
  }, [activeId]);

  // Background refresh for items: update ssh_port for pending, and tombstone deleted VMs
  React.useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      const current = loadRentals().filter(r => (r.project_id || 'default') === activeId);
      const next = [...current];
      for (const r of current) {
        try {
          // First, detect if VM still exists on provider
          const st = await vmStatusSafe(r.provider_id, r.vm_id, ads);
          if (!st.exists && st.code === 404) {
            const idx = next.findIndex(x => x.vm_id === r.vm_id && x.provider_id === r.provider_id);
            if (idx >= 0) {
              let end_reason: Rental['end_reason'] = 'unknown';
              // Try to infer depletion from chain if we have a stream_id and contract address
              try {
                const spAddr = (loadSettings().stream_payment_address || process.env.NEXT_PUBLIC_STREAM_PAYMENT_ADDRESS || '').trim();
                if (r.stream_id && spAddr) {
                  const meta = await fetchStreamWithMeta(spAddr, BigInt(r.stream_id));
                  if (meta.remaining <= 0) end_reason = 'stream_depleted';
                }
              } catch {}
              next[idx] = { ...next[idx], status: 'terminated', ssh_port: null, end_reason, ended_at: Math.floor(Date.now()/1000) } as Rental;
            }
            continue; // no need to check access for non-existent VM
          }
          // For existing VMs with missing ssh_port, try to resolve access
          if (!r.ssh_port) {
            try {
              const acc = await vmAccess(r.provider_id, r.vm_id, ads);
              if (acc && acc.ssh_port) {
                const idx = next.findIndex(x => x.vm_id === r.vm_id && x.provider_id === r.provider_id);
                if (idx >= 0) next[idx] = { ...next[idx], ssh_port: acc.ssh_port, status: 'running' } as Rental;
              } else {
                const idx = next.findIndex(x => x.vm_id === r.vm_id && x.provider_id === r.provider_id);
                if (idx >= 0 && !next[idx].status) next[idx] = { ...next[idx], status: 'creating' } as Rental;
              }
            } catch {}
          }
        } catch {}
        if (cancelled) return;
      }
      saveRentals(next);
      setItems(next);
    };
    const iv = setInterval(tick, 7000);
    tick();
    return () => { cancelled = true; clearInterval(iv); };
  }, [activeId, ads]);

  const copySSH = async (r: Rental) => {
    try {
      setBusyId(r.vm_id);
      let port = r.ssh_port || undefined;
      let host = r.provider_ip || undefined;
      if (!port) {
        try { const acc = await vmAccess(r.provider_id, r.vm_id, ads); port = acc?.ssh_port || port; } catch {}
      }
      if (!host) host = r.provider_ip || 'PROVIDER_IP';
      if (!port) { show("Could not resolve SSH port"); return; }
      const cmd = buildSshCommand(host, Number(port));
      const ok = await copyText(cmd);
      show(ok ? "SSH command copied" : "Copy failed");
    } catch (e) {
      show("Copy failed");
    } finally {
      setBusyId(null);
    }
  };

  const visible = items.filter(r => (r.project_id || 'default') === activeId && !['terminated', 'deleted'].includes((r.status || '').toLowerCase()));
  if (!visible.length) return null;

  const projectName = projects.find(p => p.id === activeId)?.name || activeId;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2>{projectName} — Machines</h2>
        <div className="text-sm text-gray-600">{visible.length} total</div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        {visible.map(r => (
          <VmCard
            key={r.vm_id}
            rental={r}
            busy={busyId === r.vm_id}
            onCopySSH={(vm) => { copySSH(vm); }}
            showStreamMeta={false}
            showStop={false}
            showDestroy={false}
          />
        ))}
      </div>

      <StreamsMini projectId={activeId} />
    </div>
  );
}
