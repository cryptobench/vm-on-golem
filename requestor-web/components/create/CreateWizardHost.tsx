"use client";
import React from "react";
import { useRouter, usePathname } from "next/navigation";
import { CreateWizard } from "./CreateWizard";

export function CreateWizardHost() {
  const router = useRouter();
  const [open, setOpen] = React.useState(false);
  const pathname = usePathname();

  React.useEffect(() => {
    const handler = () => setOpen(true);
    window.addEventListener('requestor-open-create-wizard', handler as EventListener);
    return () => window.removeEventListener('requestor-open-create-wizard', handler as EventListener);
  }, []);

  // Close wizard on route changes so navigation from the sidebar or elsewhere
  // never leaves the overlay visible on the new route.
  React.useEffect(() => {
    if (open) setOpen(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  const onComplete = (data: { countries?: string[]; cpu?: number; memory?: number; storage?: number; platform?: string; sshKeyId?: string; max_usd_per_month?: number; provider_id?: string }) => {
    try {
      localStorage.setItem('requestor_pending_create', JSON.stringify(data));
      if (data.provider_id) localStorage.setItem('requestor_pending_rent', data.provider_id);
    } catch {}
    setOpen(false);
    router.push('/providers');
  };

  return (
    <CreateWizard open={open} onClose={() => setOpen(false)} onComplete={onComplete} />
  );
}
