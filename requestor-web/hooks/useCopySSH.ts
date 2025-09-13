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
        try { const acc = await vmAccess(r.provider_id, r.vm_id, ads); port = acc?.ssh_port || port; } catch {}
      }
      if (!host) host = r.provider_ip || 'PROVIDER_IP';
      if (!port) { show('Could not resolve SSH port'); return false; }
      const cmd = buildSshCommand(host, Number(port));
      const ok = await copyText(cmd);
      show(ok ? 'SSH command copied' : 'Copy failed');
      return ok;
    } catch {
      show('Copy failed');
      return false;
    }
  };
}

