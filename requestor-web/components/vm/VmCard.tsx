"use client";
import React from "react";
import { useRouter } from "next/navigation";
import type { Rental } from "../../lib/api";
import { Spinner } from "../ui/Spinner";
import { StatusBadge } from "../ui/StatusBadge";
import { RiCpuLine, RiStackLine, RiHardDrive2Line } from "@remixicon/react";
import { humanDuration } from "../../lib/streams";

// StatusBadge imported from shared UI

type VmCardProps = {
  rental: Rental;
  busy?: boolean;
  remainingSeconds?: number | null;
  onCopySSH?: (r: Rental) => void;
  onStop?: (r: Rental) => void;
  onDestroy?: (r: Rental) => void;
  showStreamMeta?: boolean; // show Stream and Remaining rows
  showCopy?: boolean;
  showStop?: boolean;
  showDestroy?: boolean;
};

export function VmCard({ rental: r, busy, remainingSeconds, onCopySSH, onStop, onDestroy, showStreamMeta = true, showCopy = true, showStop = true, showDestroy = true }: VmCardProps) {
  const router = useRouter();
  const isTerminated = (r.status || '').toLowerCase() === 'terminated' || (r.status || '').toLowerCase() === 'deleted';

  return (
    <div
      className={"box-border flex flex-col border bg-white px-6 py-6 " + (isTerminated ? "opacity-90" : "hover:border-gray-300 cursor-pointer") }
      role="button"
      onClick={() => router.push(`/vm?id=${encodeURIComponent(r.vm_id)}`)}
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); router.push(`/vm?id=${encodeURIComponent(r.vm_id)}`); } }}
    >
      <div className="flex flex-row items-start gap-4">
        {/* Main info */}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 min-w-0">
            <StatusBadge status={r.status || (r.ssh_port ? 'running' : 'creating')} />
            <a className="truncate text-base font-medium text-gray-900 hover:underline" href={`/vm?id=${encodeURIComponent(r.vm_id)}`}>{r.name}</a>
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-gray-600">
            <span className="font-mono break-all" title={r.provider_id}>Provider: {r.provider_id}</span>
            <span className="font-mono break-all" title={r.vm_id}>VM: {r.vm_id}</span>
            {r.platform && (
              <span className="rounded border px-1.5 py-0.5 text-[11px] text-gray-700" title="Architecture">{r.platform}</span>
            )}
          </div>
          {/* Specs and platform badges */}
          {(r.resources || r.platform) && (
            <div className="mt-2 flex flex-row flex-wrap items-center gap-4 text-[12px] text-gray-700">
              {r.resources?.cpu != null && (
                <span className="inline-flex items-center gap-1.5"><RiCpuLine className="h-4 w-4 text-gray-500" /> Cores: <span className="font-mono">{r.resources.cpu}</span></span>
              )}
              {r.resources?.memory != null && (
                <span className="inline-flex items-center gap-1.5"><RiStackLine className="h-4 w-4 text-gray-500" /> Memory: <span className="font-mono">{r.resources.memory} GB</span></span>
              )}
              {r.resources?.storage != null && (
                <span className="inline-flex items-center gap-1.5"><RiHardDrive2Line className="h-4 w-4 text-gray-500" /> Disk: <span className="font-mono">{r.resources.storage} GB</span></span>
              )}
            </div>
          )}
          {showStreamMeta && (
            <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2 text-sm text-gray-700">
              <div>
                <div className="text-gray-500">Stream</div>
                <div className="truncate">{r.stream_id ? `#${r.stream_id}` : '—'}</div>
              </div>
              <div>
                <div className="text-gray-500">Remaining</div>
                <div>{isTerminated ? (r.end_reason === 'stream_depleted' ? '0s' : '—') : (r.stream_id ? (remainingSeconds != null ? humanDuration(remainingSeconds) : <span className="text-gray-400">fetching…</span>) : '—')}</div>
              </div>
            </div>
          )}
        </div>
        {/* Actions */}
        {(showCopy || showStop || showDestroy) && (
          <div className="flex w-full max-w-[220px] flex-col items-stretch gap-2 sm:w-auto sm:items-end">
            {showCopy && !isTerminated && (
              <button className="btn btn-secondary w-full sm:w-auto" onClick={(e) => { e.stopPropagation(); onCopySSH?.(r); }} disabled={!!busy || isTerminated}>
                {busy ? <><Spinner className="h-4 w-4" /> Copy SSH</> : 'Copy SSH'}
              </button>
            )}
            {showStop && (
              <button className="btn btn-secondary w-full sm:w-auto" onClick={(e) => { e.stopPropagation(); onStop?.(r); }} disabled={!!busy || isTerminated}>
                {busy ? <><Spinner className="h-4 w-4" /> Stop</> : 'Stop'}
              </button>
            )}
            {showDestroy && (
              <button className="btn btn-danger w-full sm:w-auto" onClick={(e) => { e.stopPropagation(); onDestroy?.(r); }} disabled={!!busy}>
                {busy ? <><Spinner className="h-4 w-4" /> Destroy</> : 'Destroy'}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
