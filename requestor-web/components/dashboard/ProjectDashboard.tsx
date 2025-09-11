"use client";
import React from "react";
import { loadRentals, saveRentals, vmAccess, type Rental } from "../../lib/api";
import { useProjects } from "../../context/ProjectsContext";
import { useAds } from "../../context/AdsContext";
import { useToast } from "../ui/Toast";
import { Spinner } from "../ui/Spinner";
import { StreamsMini } from "./StreamsMini";

function StatusBadge({ status }: { status?: string | null }) {
  const s = (status || '').toLowerCase();
  if (s === 'running') {
    return <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">● Running</span>;
  }
  if (s === 'creating') {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
        <Spinner className="h-3.5 w-3.5" /> Creating
      </span>
    );
  }
  if (s === 'error' || s === 'failed') {
    return <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">● Error</span>;
  }
  if (s === 'stopped') {
    return <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-700">● Stopped</span>;
  }
  // Default/fallback
  return <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700">● Unknown</span>;
}

function fmtMono(s: string | number | null | undefined) {
  return <span className="font-mono text-xs sm:text-sm">{s ?? "—"}</span>;
}

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

  // Background refresh for items being created: fetch access to update ssh_port and status
  React.useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      const current = loadRentals().filter(r => (r.project_id || 'default') === activeId);
      const pending = current.filter(r => !r.ssh_port);
      if (!pending.length) return;
      // Refresh each pending item once per tick
      const next = [...current];
      for (const r of pending) {
        try {
          const acc = await vmAccess(r.provider_id, r.vm_id, ads);
          if (acc && acc.ssh_port) {
            const idx = next.findIndex(x => x.vm_id === r.vm_id && x.provider_id === r.provider_id);
            if (idx >= 0) next[idx] = { ...next[idx], ssh_port: acc.ssh_port, status: 'running' } as Rental;
          } else {
            const idx = next.findIndex(x => x.vm_id === r.vm_id && x.provider_id === r.provider_id);
            if (idx >= 0 && !next[idx].status) next[idx] = { ...next[idx], status: 'creating' } as Rental;
          }
        } catch {
          // leave as-is
        }
        if (cancelled) return;
      }
      saveRentals(next);
      setItems(next);
    };
    const iv = setInterval(tick, 5000);
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
      if (!port) {
        show("Could not resolve SSH port");
        return;
      }
      // Match requestor CLI format: ssh -i <key> -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p <port> ubuntu@<host>
      const keyPath = "~/.golem/requestor/ssh/golem_id_rsa"; // default Golem key path used by requestor CLI when system key isn't used
      const cmd = `ssh -i ${keyPath} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p ${port} ubuntu@${host}`;
      await navigator.clipboard.writeText(cmd);
      show("SSH command copied");
    } catch (e) {
      show("Could not copy SSH command");
    } finally {
      setBusyId(null);
    }
  };

  if (!items.length) return null;

  const projectName = projects.find(p => p.id === activeId)?.name || activeId;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2>{projectName} — Machines</h2>
        <div className="text-sm text-gray-600">{items.length} total</div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        {items.map(r => (
          <a key={r.vm_id} href={`/vm?id=${encodeURIComponent(r.vm_id)}`} className="card group hover:shadow-md transition-shadow">
            <div className="card-body">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2 min-w-0">
                  <StatusBadge status={r.status || (r.ssh_port ? 'running' : 'creating')} />
                  <div className="font-semibold truncate group-hover:underline">{r.name}</div>
                </div>
                <div className="text-xs text-gray-500">{fmtMono(r.provider_id)}</div>
              </div>
              <div className="mt-2 grid grid-cols-2 gap-2 text-sm text-gray-700">
                <div>
                  <div className="text-gray-500">VM ID</div>
                  <div className="truncate">{fmtMono(r.vm_id)}</div>
                </div>
                <div>
                  <div className="text-gray-500">SSH</div>
                  <div className="truncate">{r.provider_ip ? `${r.provider_ip}:${r.ssh_port ?? '—'}` : '—'}</div>
                </div>
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <button
                  className="btn btn-secondary"
                  onClick={(e) => { e.preventDefault(); e.stopPropagation(); copySSH(r); }}
                  disabled={busyId === r.vm_id}
                >
                  {busyId === r.vm_id ? <><Spinner className="h-4 w-4" /> Copy SSH</> : 'Copy SSH'}
                </button>
              </div>
            </div>
          </a>
        ))}
      </div>

      <StreamsMini projectId={activeId} />
    </div>
  );
}
