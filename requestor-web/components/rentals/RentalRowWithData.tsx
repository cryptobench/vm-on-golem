"use client";
import React from "react";
import { useRouter } from "next/navigation";
import { RiCpuLine, RiHardDrive2Line, RiStackLine } from "@remixicon/react";
import { useProviderInfo, useVmAccess, useVmStatus, useVmStreamStatus } from "../../hooks/useApiSWR";
import type { Rental } from "../../lib/api";
import { StatusBadge } from "../ui/StatusBadge";
import { Spinner } from "../ui/Spinner";
import { humanDuration } from "../../lib/streams";
import { countryFlagEmoji } from "../../lib/intl";
import { ConfirmDialog } from "../ui/ConfirmDialog";

export function RentalRowWithData({
  rental,
  busy,
  onCopySSH,
  onDestroy,
}: {
  rental: Rental;
  busy?: boolean;
  onCopySSH?: (r: Rental) => void;
  onDestroy?: (r: Rental) => void;
}) {
  const router = useRouter();
  const [confirmOpen, setConfirmOpen] = React.useState(false);
  const { data: provider } = useProviderInfo(rental.provider_id, { refreshInterval: 30000 });
  const { data: access } = useVmAccess(rental.provider_id, rental.vm_id, { refreshInterval: 8000 });
  const { data: status } = useVmStatus(rental.provider_id, rental.vm_id, { refreshInterval: 8000 });
  const { data: stream } = useVmStreamStatus(rental.provider_id, rental.vm_id, { refreshInterval: 15000 });

  // Derive status carefully to preserve terminal states
  let st: string = String((status as any)?.status || rental.status || '').toLowerCase();
  const sshPort = (access as any)?.ssh_port ?? (status as any)?.ssh_port ?? rental.ssh_port;
  if (!st) st = sshPort ? 'running' : 'creating';
  const isTerminated = st === 'terminated' || st === 'deleted';
  const remaining = (stream as any)?.computed?.remaining_seconds != null ? Number((stream as any).computed.remaining_seconds) : null;
  const spec = rental.resources;

  return (
    <div
      className="box-border flex flex-col border bg-white px-6 py-6 cursor-pointer select-none hover:border-gray-300"
      onClick={() => router.push(`/vm?id=${encodeURIComponent(rental.vm_id)}`)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); router.push(`/vm?id=${encodeURIComponent(rental.vm_id)}`); } }}
    >
      <div className="flex flex-row items-center gap-4">
        {/* Main info (mirrors ProviderRow layout) */}
        <div className="flex w-full min-w-0 flex-[2] flex-row items-start gap-4">
          <div className="flex min-w-0 flex-1 flex-col justify-center gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <StatusBadge status={st} />
              {(() => { const flag = countryFlagEmoji((provider as any)?.country || ''); return flag ? <span className="text-base leading-none" title={(provider as any)?.country || ''}>{flag}</span> : null; })()}
              <div className="truncate text-base font-medium text-gray-900" title={rental.name}>{rental.name}</div>
            </div>
            <div className="flex items-center gap-3 text-xs text-gray-500">
              <span className="font-mono break-all" title={rental.vm_id}>VM: {rental.vm_id}</span>
              <span className="font-mono break-all" title={rental.provider_id}>Provider: {rental.provider_id}</span>
              {((provider as any)?.platform || rental.platform) && (
                <span className="rounded border px-1.5 py-0.5 text-[11px] text-gray-700">{(provider as any)?.platform || rental.platform}</span>
              )}
              {((provider as any)?.ip_address || rental.provider_ip) && (
                <span className="text-gray-600">{(provider as any)?.ip_address || rental.provider_ip}</span>
              )}
            </div>
            {(spec) && (
              <div className="mt-2 flex flex-row flex-wrap items-center gap-4 text-[12px] text-gray-700">
                <span className="inline-flex items-center gap-1.5">
                  <RiCpuLine className="h-4 w-4 text-gray-500" /> vCPU: <span className="font-mono">{spec.cpu}</span>
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <RiStackLine className="h-4 w-4 text-gray-500" /> RAM: <span className="font-mono">{spec.memory} GB</span>
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <RiHardDrive2Line className="h-4 w-4 text-gray-500" /> Storage: <span className="font-mono">{spec.storage} GB</span>
                </span>
              </div>
            )}
            <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2 text-[12px] text-gray-700">
              <div>
                <div className="text-gray-500">Stream</div>
                <div className="truncate">{rental.stream_id ? `#${rental.stream_id}` : '—'}</div>
              </div>
              <div>
                <div className="text-gray-500">Remaining</div>
                <div>{rental.stream_id ? (remaining != null ? humanDuration(remaining) : <span className="text-gray-400">fetching…</span>) : '—'}</div>
              </div>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex w-full max-w-[260px] flex-col items-stretch gap-2 sm:w-auto sm:items-end">
          {!isTerminated && (
            <button className="btn btn-secondary w-full sm:w-auto" onClick={(e) => { e.stopPropagation(); onCopySSH?.(rental); }} disabled={!!busy}>
              {busy ? <><Spinner className="h-4 w-4" /> Copy SSH</> : 'Copy SSH'}
            </button>
          )}
          <button className="btn btn-danger w-full sm:w-auto" onClick={(e) => { e.stopPropagation(); setConfirmOpen(true); }} disabled={!!busy}>
            {busy ? <><Spinner className="h-4 w-4" /> Terminate</> : 'Terminate'}
          </button>
      </div>
      </div>
      <ConfirmDialog
        open={confirmOpen}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={() => { setConfirmOpen(false); onDestroy?.(rental); }}
        title="Terminate VM"
        description="Are you sure you want to permanently terminate this VM? This action cannot be undone."
        confirmLabel="Terminate"
        danger
        busy={!!busy}
      />
    </div>
  );
}
