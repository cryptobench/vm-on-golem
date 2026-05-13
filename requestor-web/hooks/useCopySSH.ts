"use client";
import { useToast } from "@golem/ui";
import { buildSshCommand, copyText } from "../lib/ssh";
import { vmAccess, type Rental } from "../lib/api";
import { useAds } from "../context/AdsContext";

export function useCopySSH() {
  const { show } = useToast();
  const { ads } = useAds();
  return async function copySSH(r: Rental): Promise<boolean> {
    try {
      const acc = await vmAccess(r.provider_id, r.vm_id, ads);
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
