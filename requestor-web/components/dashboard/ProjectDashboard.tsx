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
  const [busyId, setBusyId] = React.useState<string | null>(null);

  // Reconcile handled by hook; keep additional enrichers below as needed

  const copySSHAction = useCopySSH();
  const copySSH = async (r: Rental) => { setBusyId(r.vm_id); try { await copySSHAction(r); } finally { setBusyId(null); } };

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
