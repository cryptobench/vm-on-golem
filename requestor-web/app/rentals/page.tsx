"use client";
import React from "react";
import { loadRentals, saveRentals, vmAccess, vmStop, vmDestroy, type Rental } from "../../lib/api";
import { useCopySSH } from "../../hooks/useCopySSH";
import { useToast } from "../../components/ui/Toast";
import { useAds } from "../../context/AdsContext";
import { Spinner } from "../../components/ui/Spinner";
import { Skeleton } from "../../components/ui/Skeleton";
import { useProjects } from "../../context/ProjectsContext";
import { useProjectRentals } from "../../hooks/useProjectRentals";
import { VmCard } from "../../components/vm/VmCard";
import { VmCardWithData } from "../../components/vm/VmCardWithData";
import { StatusBadge } from "../../components/ui/StatusBadge";

// StatusBadge now imported from shared UI

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
  const [itemsRaw, setItemsRaw] = React.useState<ReturnType<typeof loadRentals> | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [busyId, setBusyId] = React.useState<string | null>(null);
  const { ads } = useAds();
  const { show } = useToast();
  const { activeId } = useProjects();
  const { items, setItems, refresh } = useProjectRentals(activeId);

  React.useEffect(() => { const t = setTimeout(() => refresh(), 200); return () => clearTimeout(t); }, [refresh]);

  // Remaining seconds handled per-card via SWR + 1s ticker

  // Project-level reconcile handled by useProjectRentals

  const copySSHAction = useCopySSH();
  const copySSH = async (r: any) => { setError(null); setBusyId(r.vm_id); try { await copySSHAction(r); } finally { setBusyId(null); } };
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
                  <VmCardWithData
                    key={r.vm_id}
                    rental={r}
                    busy={busyId === r.vm_id}
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
                    onDestroy={destroy}
                    showStreamMeta={true}
                    showCopy={false}
                    showStop={false}
                    showDestroy={false}
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
