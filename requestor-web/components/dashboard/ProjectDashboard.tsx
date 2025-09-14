"use client";
import React from "react";
import { loadRentals, saveRentals, vmAccess, vmStatusSafe, type Rental, loadSettings } from "../../lib/api";
import { fetchStreamWithMeta } from "../../lib/streams";
import { useProjects } from "../../context/ProjectsContext";
import { useAds } from "../../context/AdsContext";
import { useToast } from "../ui/Toast";
import { StreamsMini } from "./StreamsMini";
import { useCopySSH } from "../../hooks/useCopySSH";
import { VmCardWithData } from "../vm/VmCardWithData";
import { useProjectRentals } from "../../hooks/useProjectRentals";

// Using shared VmCard component for consistency

export function ProjectDashboard() {
  const { activeId, projects } = useProjects();
  const { ads } = useAds();
  const { show } = useToast();
  const { items, setItems } = useProjectRentals(activeId);
  const [mounted, setMounted] = React.useState(false);
  React.useEffect(() => { setMounted(true); }, []);
  const [busyId, setBusyId] = React.useState<string | null>(null);

  // Reconcile handled by hook; keep additional enrichers below as needed

  const copySSHAction = useCopySSH();
  const copySSH = async (r: Rental) => { setBusyId(r.vm_id); try { await copySSHAction(r); } finally { setBusyId(null); } };

  const visible = items.filter(r => (r.project_id || 'default') === activeId && !['terminated', 'deleted'].includes((r.status || '').toLowerCase()));
  if (!mounted) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h2>{projects.find(p => p.id === activeId)?.name || activeId} — Machines</h2>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          {Array.from({ length: 2 }).map((_, i) => (
            <div key={i} className="card"><div className="card-body">
              <div className="flex items-center justify-between"><div className="h-4 w-28 bg-gray-200 animate-pulse rounded" /><div className="h-4 w-10 bg-gray-200 animate-pulse rounded" /></div>
              <div className="mt-2 grid grid-cols-2 gap-2">
                <div className="h-4 w-20 bg-gray-200 animate-pulse rounded" />
                <div className="h-4 w-24 bg-gray-200 animate-pulse rounded" />
              </div>
            </div></div>
          ))}
        </div>
      </div>
    );
  }
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
          <VmCardWithData
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
