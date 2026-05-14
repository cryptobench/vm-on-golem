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
  const { data } = useVmStreamStatus(rental.provider_endpoint_url, rental.vm_id, {
    refreshInterval: 12000,
  });
  const [remaining, setRemaining] = React.useState<number | undefined>(
    undefined,
  );
  const { data: vmData } = useVmStatus(rental.provider_endpoint_url, rental.vm_id, {
    refreshInterval: 8000,
  });

  React.useEffect(() => {
    if (data?.computed?.remaining_seconds != null) {
      setRemaining(Number(data.computed.remaining_seconds));
    }
  }, [data?.computed?.remaining_seconds]);

  React.useEffect(() => {
    const iv = setInterval(
      () => setRemaining((x) => (x != null ? (x > 0 ? x - 1 : 0) : x)),
      1000,
    );
    return () => clearInterval(iv);
  }, []);

  // Merge authoritative VM status/ports (and resources if available) into local storage and the card view
  React.useEffect(() => {
    if (!vmData) return;
    const s = vmData as any;
    const status = String(s.status || "").toLowerCase();
    const sshPort = s.ssh_port != null ? Number(s.ssh_port) : null;
    const ipAddr = s.ip_address || null;
    // Try to pick resources from provider response if present
    const resFromVm = (() => {
      const r =
        s?.resources && typeof s.resources === "object" ? s.resources : s;
      const cpu = Number((r as any)?.cpu);
      const memory = Number((r as any)?.memory);
      const storage = Number((r as any)?.storage);
      if ([cpu, memory, storage].every((n) => Number.isFinite(n) && n > 0)) {
        return { cpu, memory, storage } as Rental["resources"];
      }
      return undefined;
    })();
    const nowSec = Math.floor(Date.now() / 1000);
    let next: Rental | null = null;
    if (status === "running") {
      if (
        rental.status !== "running" ||
        rental.ssh_port !== sshPort ||
        rental.provider_ip !== ipAddr ||
        (resFromVm &&
          JSON.stringify(rental.resources) !== JSON.stringify(resFromVm))
      ) {
        next = {
          ...rental,
          status: "running",
          ssh_port: sshPort,
          provider_ip: ipAddr,
          resources: resFromVm || rental.resources,
        };
      }
    } else if (status === "stopped") {
      if (
        rental.status !== "stopped" ||
        (resFromVm &&
          JSON.stringify(rental.resources) !== JSON.stringify(resFromVm))
      )
        next = {
          ...rental,
          status: "stopped",
          resources: resFromVm || rental.resources,
        };
    } else if (status === "terminated" || status === "deleted") {
      if (
        rental.status !== "terminated" ||
        (resFromVm &&
          JSON.stringify(rental.resources) !== JSON.stringify(resFromVm))
      )
        next = {
          ...rental,
          status: "terminated",
          ssh_port: null,
          ended_at: nowSec,
          resources: resFromVm || rental.resources,
        } as any;
    }
    if (next) {
      try {
        const list = loadRentals();
        const idx = list.findIndex(
          (x) =>
            x.vm_id === rental.vm_id && x.provider_id === rental.provider_id,
        );
        if (idx >= 0) {
          const out = [...list];
          out[idx] = next;
          saveRentals(out);
        }
      } catch {}
    }
  }, [
    vmData,
    rental.vm_id,
    rental.provider_id,
    rental.status,
    rental.ssh_port,
    rental.provider_ip,
  ]);

  // Create a computed rental for display using the freshest data
  const displayRental: Rental = React.useMemo(() => {
    const s = (vmData as any) || {};
    const status = s.status ? String(s.status) : rental.status;
    const sshPort = s.ssh_port != null ? Number(s.ssh_port) : null;
    const ipAddr = s.ip_address != null ? s.ip_address : rental.provider_ip;
    // Prefer resources from VM status if exposed; fallback to saved rental spec
    const r = s?.resources && typeof s.resources === "object" ? s.resources : s;
    const cpu = Number((r as any)?.cpu);
    const memory = Number((r as any)?.memory);
    const storage = Number((r as any)?.storage);
    const resources = [cpu, memory, storage].every(
      (n) => Number.isFinite(n) && n > 0,
    )
      ? { cpu, memory, storage }
      : rental.resources;
    return {
      ...rental,
      status,
      ssh_port: sshPort,
      provider_ip: ipAddr,
      resources,
    } as Rental;
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
