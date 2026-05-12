"use client";
import { useToast } from "../components/ui/Toast";
import { buildSshCommand, copyText } from "../lib/ssh";
import { vmAccess, type Rental } from "../lib/api";
import { useAds } from "../context/AdsContext";

export function useCopySSH() {
  const { show } = useToast();
  const { ads } = useAds();
  return async function copySSH(r: Rental): Promise<boolean> {
    try {
      let port = r.ssh_port || undefined;
      let host = r.provider_ip || undefined;
      if (!port) {
        const acc = await vmAccess(r.provider_id, r.vm_id, ads);
        port = acc?.ssh_port || port;
        host = host || acc?.ssh_host || undefined;
      }
      if (!host) host = r.provider_ip || 'PROVIDER_IP';
      if (!port) { show('SSH port unavailable'); return false; }
      const cmd = buildSshCommand(host, Number(port));
      const ok = await copyText(cmd);
      show(ok ? 'SSH command copied' : 'Could not copy');
      return ok;
  } catch {
      show('Could not copy');
      return false;
  }
  };
}
