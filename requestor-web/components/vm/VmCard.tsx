"use client";
import React from "react";
import type { Rental } from "../../lib/api";
import { Spinner } from "../ui/Spinner";
import { humanDuration } from "../../lib/streams";

function StatusBadge({ status }: { status?: string | null }) {
  const s = (status || '').toLowerCase();
  if (s === 'running') return <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">● Running</span>;
  if (s === 'creating') return <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700"><Spinner className="h-3.5 w-3.5" /> Creating</span>;
  if (s === 'stopped') return <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-700">● Stopped</span>;
  if (s === 'terminated' || s === 'deleted') return <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">● Terminated</span>;
  if (s === 'error' || s === 'failed') return <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">● Error</span>;
  return <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700">● Unknown</span>;
}

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
  const ssh = r.provider_ip && r.ssh_port ? `${r.provider_ip}:${r.ssh_port}` : '—';
  const isTerminated = (r.status || '').toLowerCase() === 'terminated' || (r.status || '').toLowerCase() === 'deleted';

  return (
    <div className="card">
      <div className="card-body">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2 min-w-0">
            <StatusBadge status={r.status || (r.ssh_port ? 'running' : 'creating')} />
            <a className="font-semibold truncate hover:underline" href={`/vm?id=${encodeURIComponent(r.vm_id)}`}>{r.name}</a>
          </div>
        </div>
        <div className="mt-2 grid grid-cols-2 gap-2 text-sm text-gray-700">
          <div>
            <div className="text-gray-500">VM ID</div>
            <div className="font-mono text-xs sm:text-sm truncate" title={r.vm_id}>{r.vm_id}</div>
          </div>
          <div>
            <div className="text-gray-500">SSH</div>
            <div>{isTerminated ? '—' : ssh}</div>
          </div>
          {showStreamMeta && (
            <>
              <div>
                <div className="text-gray-500">Stream</div>
                <div className="truncate">{r.stream_id ? `#${r.stream_id}` : '—'}</div>
              </div>
              <div>
                <div className="text-gray-500">Remaining</div>
                <div>{isTerminated ? (r.end_reason === 'stream_depleted' ? '0s' : '—') : (r.stream_id ? (remainingSeconds != null ? humanDuration(remainingSeconds) : <span className="text-gray-400">fetching…</span>) : '—')}</div>
              </div>
            </>
          )}
        </div>
        {(showCopy || showStop || showDestroy) && (
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {showCopy && (
              <button className="btn btn-secondary" onClick={() => onCopySSH?.(r)} disabled={!!busy || isTerminated}>
                {busy ? <><Spinner className="h-4 w-4" /> Copy SSH</> : 'Copy SSH'}
              </button>
            )}
            {showStop && (
              <button className="btn btn-secondary" onClick={() => onStop?.(r)} disabled={!!busy || isTerminated}>
                {busy ? <><Spinner className="h-4 w-4" /> Stop</> : 'Stop'}
              </button>
            )}
            {showDestroy && (
              <button className="btn btn-danger" onClick={() => onDestroy?.(r)} disabled={!!busy}>
                {busy ? <><Spinner className="h-4 w-4" /> Destroy</> : 'Destroy'}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

