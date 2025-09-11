"use client";
import React from "react";
import { loadRentals, vmAccess, type Rental } from "../../lib/api";
import { useProjects } from "../../context/ProjectsContext";
import { useAds } from "../../context/AdsContext";
import { useToast } from "../ui/Toast";
import { Spinner } from "../ui/Spinner";
import { StreamsMini } from "./StreamsMini";

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
          <div key={r.vm_id} className="card hover:shadow-md transition-shadow">
            <div className="card-body">
              <div className="flex items-start justify-between gap-3">
                <div className="font-semibold truncate">{r.name}</div>
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
                <button className="btn btn-secondary" onClick={() => copySSH(r)} disabled={busyId === r.vm_id}>
                  {busyId === r.vm_id ? <><Spinner className="h-4 w-4" /> Copy SSH</> : 'Copy SSH'}
                </button>
                <a href={`/vm/${encodeURIComponent(r.vm_id)}`} className="btn btn-secondary">Details</a>
              </div>
            </div>
          </div>
        ))}
      </div>

      <StreamsMini projectId={activeId} />
    </div>
  );
}
