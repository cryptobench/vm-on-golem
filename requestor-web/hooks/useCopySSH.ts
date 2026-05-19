"use client";
import { useToast } from "@golem/ui";
import { buildSshCommand, copyText } from "../lib/ssh";
import { vmAccess, type Rental } from "../lib/api";

export function useCopySSH() {
  const { show } = useToast();
  return async function copySSH(r: Rental): Promise<boolean> {
    try {
      if (!r.provider_endpoint_url) {
        show("Provider endpoint unavailable");
        return false;
      }
      const acc = await vmAccess(r.provider_endpoint_url, r.vm_id);
      if (!("ssh_host" in acc) || acc.ssh_port == null || !acc.ssh_user) {
        show("SSH port unavailable");
        return false;
      }
      const cmd = buildSshCommand(
        acc.ssh_host,
        Number(acc.ssh_port),
        acc.ssh_user,
      );
      const ok = await copyText(cmd);
      show(ok ? "SSH command copied" : "Could not copy");
      return ok;
    } catch {
      show("Could not copy");
      return false;
    }
  };
}
