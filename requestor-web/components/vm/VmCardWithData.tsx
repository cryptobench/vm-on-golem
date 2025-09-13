"use client";
import React from "react";
import { VmCard } from "./VmCard";
import { useVmStreamStatus, useVmStatus } from "../../hooks/useApiSWR";
import { loadRentals, saveRentals, type Rental } from "../../lib/api";

export function VmCardWithData(props: {
  rental: Rental;
  busy?: boolean;
  onCopySSH?: (r: Rental) => void;
  onStop?: (r: Rental) => void;
  onDestroy?: (r: Rental) => void;
  showStreamMeta?: boolean;
  showCopy?: boolean;
  showStop?: boolean;
  showDestroy?: boolean;
}) {
  const { rental } = props;
  const { data } = useVmStreamStatus(rental.provider_id, rental.vm_id, { refreshInterval: 12000 });
  const [remaining, setRemaining] = React.useState<number | undefined>(undefined);
  const { data: vmData } = useVmStatus(rental.provider_id, rental.vm_id, { refreshInterval: 8000 });

  React.useEffect(() => {
    if (data?.computed?.remaining_seconds != null) {
      setRemaining(Number(data.computed.remaining_seconds));
    }
  }, [data?.computed?.remaining_seconds]);

  React.useEffect(() => {
    const iv = setInterval(() => setRemaining((x) => (x != null ? (x > 0 ? x - 1 : 0) : x)), 1000);
    return () => clearInterval(iv);
  }, []);

  // Merge authoritative VM status/ports into local storage and into the card view
  React.useEffect(() => {
    if (!vmData) return;
    const s = vmData as any;
    const status = String(s.status || '').toLowerCase();
    const sshPort = s.ssh_port != null ? Number(s.ssh_port) : null;
    const ipAddr = s.ip_address || null;
    const nowSec = Math.floor(Date.now()/1000);
    let next: Rental | null = null;
    if (status === 'running') {
      if (rental.status !== 'running' || rental.ssh_port !== sshPort || rental.provider_ip !== ipAddr) {
        next = { ...rental, status: 'running', ssh_port: sshPort, provider_ip: ipAddr };
      }
    } else if (status === 'stopped') {
      if (rental.status !== 'stopped') next = { ...rental, status: 'stopped' };
    } else if (status === 'terminated' || status === 'deleted') {
      if (rental.status !== 'terminated') next = { ...rental, status: 'terminated', ssh_port: null, ended_at: nowSec } as any;
    }
    if (next) {
      try {
        const list = loadRentals();
        const idx = list.findIndex(x => x.vm_id === rental.vm_id && x.provider_id === rental.provider_id);
        if (idx >= 0) { const out = [...list]; out[idx] = next; saveRentals(out); }
      } catch {}
    }
  }, [vmData, rental.vm_id, rental.provider_id, rental.status, rental.ssh_port, rental.provider_ip]);

  // Create a computed rental for display using the freshest data
  const displayRental: Rental = React.useMemo(() => {
    const s = (vmData as any) || {};
    const status = s.status ? String(s.status) : rental.status;
    const sshPort = s.ssh_port != null ? Number(s.ssh_port) : rental.ssh_port;
    const ipAddr = s.ip_address != null ? s.ip_address : rental.provider_ip;
    return { ...rental, status, ssh_port: sshPort, provider_ip: ipAddr } as Rental;
  }, [vmData, rental]);

  return (
    <VmCard
      rental={displayRental}
      busy={props.busy}
      remainingSeconds={remaining}
      onCopySSH={props.onCopySSH}
      onStop={props.onStop}
      onDestroy={props.onDestroy}
      showStreamMeta={props.showStreamMeta}
      showCopy={props.showCopy}
      showStop={props.showStop}
      showDestroy={props.showDestroy}
    />
  );
}
