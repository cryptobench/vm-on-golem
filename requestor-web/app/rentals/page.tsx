"use client";
import React from "react";
import { loadRentals, saveRentals, vmAccess, vmStop, vmDestroy } from "../../lib/api";
import { useAds } from "../../context/AdsContext";
import { Spinner } from "../../components/ui/Spinner";
import { TableSkeleton } from "../../components/ui/Skeleton";
import { useProjects } from "../../context/ProjectsContext";

export default function RentalsPage() {
  const [items, setItems] = React.useState<ReturnType<typeof loadRentals> | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [busyId, setBusyId] = React.useState<string | null>(null);
  const { ads } = useAds();
  const { projects, activeId } = useProjects();

  const refresh = () => setItems(loadRentals());

  React.useEffect(() => {
    const t = setTimeout(() => refresh(), 200); // brief delay for skeleton effect
    return () => clearTimeout(t);
  }, []);

  const access = async (r: any) => {
    setError(null); setBusyId(r.vm_id);
    try {
      const acc = await vmAccess(r.provider_id, r.vm_id, ads);
      alert(`SSH: ${r.provider_ip || 'PROVIDER_IP'}:${acc.ssh_port}`);
    } catch (e: any) { setError(e?.message || String(e)); } finally { setBusyId(null); }
  };
  const stop = async (r: any) => {
    setError(null); setBusyId(r.vm_id);
    try { await vmStop(r.provider_id, r.vm_id, ads); alert('Stop requested'); } catch (e: any) { setError(e?.message || String(e)); } finally { setBusyId(null); }
  };
  const destroy = async (r: any) => {
    if (!confirm('Destroy VM?')) return;
    setError(null); setBusyId(r.vm_id);
    try {
      await vmDestroy(r.provider_id, r.vm_id, ads);
      const cur = items || [];
      const left = cur.filter(i => i.vm_id !== r.vm_id);
      saveRentals(left);
      setItems(left);
    } catch (e: any) { setError(e?.message || String(e)); } finally { setBusyId(null); }
  };

  return (
    <div className="space-y-4">
      <h2>Your Rentals</h2>
      {error && <div className="text-sm text-red-600">{error}</div>}
      {items === null ? (
        <TableSkeleton rows={4} cols={5} />
      ) : !items.filter(i => (i.project_id || 'default') === activeId).length ? (
        <div className="text-gray-600">No VMs yet. Rent one from the Providers tab.</div>
      ) : (
        <div className="card">
          <div className="card-body overflow-x-auto">
            <table className="table">
              <thead className="bg-gray-50">
                <tr>
                  <th className="th">Name</th>
                  <th className="th">Project</th>
                  <th className="th">Provider</th>
                  <th className="th">VM ID</th>
                  <th className="th">Stream</th>
                  <th className="th">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {items.filter(r => (r.project_id || 'default') === activeId).map(r => (
                  <tr key={r.vm_id} className="hover:bg-gray-50/50">
                    <td className="td">{r.name}</td>
                    <td className="td">
                      <select
                        className="input"
                        value={r.project_id || 'default'}
                        onChange={(e) => {
                          const pid = e.target.value;
                          const next = (items || []).map(it => it.vm_id === r.vm_id ? { ...it, project_id: pid } : it);
                          saveRentals(next);
                          setItems(next);
                        }}
                      >
                        {projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                      </select>
                    </td>
                    <td className="td font-mono text-xs sm:text-sm">{r.provider_id}</td>
                    <td className="td font-mono text-xs sm:text-sm">{r.vm_id}</td>
                    <td className="td">{r.stream_id || '—'}</td>
                    <td className="td">
                      <div className="flex flex-wrap items-center gap-2">
                        <button className="btn btn-secondary" onClick={() => access(r)} disabled={busyId === r.vm_id}>{busyId === r.vm_id ? <><Spinner className="h-4 w-4" /> Access</> : 'Access'}</button>
                        <button className="btn btn-secondary" onClick={() => stop(r)} disabled={busyId === r.vm_id}>{busyId === r.vm_id ? <><Spinner className="h-4 w-4" /> Stop</> : 'Stop'}</button>
                        <button className="btn btn-danger" onClick={() => destroy(r)} disabled={busyId === r.vm_id}>{busyId === r.vm_id ? <><Spinner className="h-4 w-4" /> Destroy</> : 'Destroy'}</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
