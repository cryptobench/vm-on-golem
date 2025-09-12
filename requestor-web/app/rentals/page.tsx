"use client";
import React from "react";
import { loadRentals, saveRentals, vmAccess, vmStop, vmDestroy, vmStreamStatus, type Rental } from "../../lib/api";
import { buildSshCommand, copyText } from "../../lib/ssh";
import { useToast } from "../../components/ui/Toast";
import { useAds } from "../../context/AdsContext";
import { Spinner } from "../../components/ui/Spinner";
import { Skeleton } from "../../components/ui/Skeleton";
import { useProjects } from "../../context/ProjectsContext";
import { VmCard } from "../../components/vm/VmCard";

function StatusBadge({ status }: { status?: string | null }) {
  const s = (status || '').toLowerCase();
  if (s === 'running') return <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">● Running</span>;
  if (s === 'creating') return <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700"><Spinner className="h-3.5 w-3.5" /> Creating</span>;
  if (s === 'stopped') return <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-700">● Stopped</span>;
  if (s === 'terminated' || s === 'deleted') return <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">● Terminated</span>;
  if (s === 'error' || s === 'failed') return <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">● Error</span>;
  return <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700">● Unknown</span>;
}

function humanDuration(totalSec: number): string {
  const s = Math.max(0, Math.floor(totalSec));
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  const parts: string[] = [];
  if (d) parts.push(`${d}d`);
  if (h) parts.push(`${h}h`);
  if (m) parts.push(`${m}m`);
  if (sec && !parts.length) parts.push(`${sec}s`);
  return parts.length ? parts.join(' ') : '0s';
}

export default function RentalsPage() {
  const [items, setItems] = React.useState<ReturnType<typeof loadRentals> | null>(null);
  const [remaining, setRemaining] = React.useState<Record<string, number>>({});
  const [error, setError] = React.useState<string | null>(null);
  const [busyId, setBusyId] = React.useState<string | null>(null);
  const { ads } = useAds();
  const { show } = useToast();
  const { activeId } = useProjects();

  const refresh = () => setItems(loadRentals());

  React.useEffect(() => {
    const t = setTimeout(() => refresh(), 200); // brief delay for skeleton effect
    return () => clearTimeout(t);
  }, []);

  // Fetch per-VM stream remaining (provider computes from chain) and set countdowns
  React.useEffect(() => {
    if (!items) return;
    const list = items.filter(i => (i.project_id || 'default') === activeId && !!i.stream_id) as Rental[];
    (async () => {
      const next: Record<string, number> = {};
      for (const r of list) {
        try {
          const st = await vmStreamStatus(r.provider_id, r.vm_id, ads);
          next[r.vm_id] = st?.computed?.remaining_seconds ?? 0;
        } catch {}
      }
      setRemaining(next);
    })();
  }, [items, activeId, ads]);

  // Local 1s ticker for remaining seconds
  React.useEffect(() => {
    const iv = setInterval(() => {
      setRemaining(prev => {
        const out: Record<string, number> = {};
        for (const [k, v] of Object.entries(prev)) out[k] = v > 0 ? v - 1 : 0;
        return out;
      });
    }, 1000);
    return () => clearInterval(iv);
  }, []);

  // Background reconcile to tombstone deleted VMs
  React.useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      const list = loadRentals();
      const next = [...list];
      let changed = false;
      for (let i = 0; i < next.length; i++) {
        const r = next[i] as any;
        // Only check those in active project for efficiency
        if ((r.project_id || 'default') !== activeId) continue;
        try {
          const { vmStatusSafe } = await import('../../lib/api');
          const st = await vmStatusSafe(r.provider_id, r.vm_id, ads);
          if (!st.exists && st.code === 404) {
            if (r.status !== 'terminated') {
              next[i] = { ...r, status: 'terminated', ssh_port: null, ended_at: Math.floor(Date.now()/1000) };
              changed = true;
            }
          }
        } catch {}
        if (cancelled) return;
      }
      if (changed) {
        saveRentals(next as any);
        setItems(next as any);
      }
    };
    const iv = setInterval(tick, 8000);
    tick();
    return () => { cancelled = true; clearInterval(iv); };
  }, [activeId, ads]);

  const copySSH = async (r: any) => {
    setError(null); setBusyId(r.vm_id);
    try {
      let port = r.ssh_port || undefined;
      let host = r.provider_ip || undefined;
      if (!port) {
        try { const acc = await vmAccess(r.provider_id, r.vm_id, ads); port = acc?.ssh_port || port; } catch {}
      }
      if (!host) host = r.provider_ip || 'PROVIDER_IP';
      if (!port) { show('Could not resolve SSH port'); return; }
      const cmd = buildSshCommand(host, Number(port));
      const ok = await copyText(cmd);
      show(ok ? 'SSH command copied' : 'Copy failed');
    } catch (e: any) { setError(e?.message || String(e)); }
    finally { setBusyId(null); }
  };
  const stop = async (r: any) => {
    setError(null); setBusyId(r.vm_id);
    try { await vmStop(r.provider_id, r.vm_id, ads); alert('Stop requested'); } catch (e: any) { setError(e?.message || String(e)); } finally { setBusyId(null); }
  };
  const destroy = async (r: any) => {
    if (!confirm('Destroy VM?')) return;
    setError(null); setBusyId(r.vm_id);
    try {
      try { await vmDestroy(r.provider_id, r.vm_id, ads); } catch (e) { /* treat 404 as already deleted */ }
      const cur = items || [];
      const left = cur.filter(i => i.vm_id !== r.vm_id);
      saveRentals(left);
      setItems(left);
    } catch (e: any) { setError(e?.message || String(e)); } finally { setBusyId(null); }
  };

  const projectItems = (items || []).filter(i => (i.project_id || 'default') === activeId) as Rental[];
  const active = projectItems.filter(r => !['terminated', 'deleted'].includes((r.status || '').toLowerCase()));
  const terminated = projectItems.filter(r => ['terminated', 'deleted'].includes((r.status || '').toLowerCase()));

  return (
    <div className="space-y-6">
      <h2>Your Rentals</h2>
      {error && <div className="text-sm text-red-600">{error}</div>}
      {items === null ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="card"><div className="card-body">
              <div className="flex items-center justify-between"><Skeleton className="h-4 w-24" /><Skeleton className="h-4 w-16" /></div>
              <div className="mt-2 grid grid-cols-2 gap-2">
                <Skeleton className="h-4 w-28" />
                <Skeleton className="h-4 w-36" />
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-4 w-20" />
              </div>
              <div className="mt-3 flex gap-2">
                <Skeleton className="h-9 w-24" />
                <Skeleton className="h-9 w-24" />
                <Skeleton className="h-9 w-24" />
              </div>
            </div></div>
          ))}
        </div>
      ) : (
        <>
          {active.length ? (
            <div>
              <div className="mb-2 text-sm text-gray-700">Active</div>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {active.map((r: Rental) => (
                  <VmCard
                    key={r.vm_id}
                    rental={r}
                    busy={busyId === r.vm_id}
                    remainingSeconds={remaining[r.vm_id]}
                    onCopySSH={copySSH}
                    onStop={stop}
                    onDestroy={destroy}
                    showStreamMeta={true}
                    showCopy={true}
                    showStop={true}
                    showDestroy={true}
                  />
                ))}
              </div>
            </div>
          ) : (
            <div className="text-gray-600">No active VMs. Rent one from the Providers tab.</div>
          )}

          {terminated.length > 0 && (
            <div>
              <div className="mt-4 mb-2 text-sm text-gray-700">Terminated</div>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {terminated.map((r: Rental) => (
                  <VmCard
                    key={r.vm_id}
                    rental={r}
                    busy={busyId === r.vm_id}
                    remainingSeconds={remaining[r.vm_id]}
                    onDestroy={destroy}
                    showStreamMeta={true}
                    showCopy={false}
                    showStop={false}
                    showDestroy={true}
                  />
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
