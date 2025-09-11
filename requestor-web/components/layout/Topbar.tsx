"use client";
import Link from "next/link";
import { Spinner } from "../ui/Spinner";
import React from "react";
import { useRouter, usePathname } from "next/navigation";
import { CreateWizard } from "../create/CreateWizard";
import { useWallet } from "../../context/WalletContext";

export function Topbar({ busy = false }: { busy?: boolean }) {
  const [open, setOpen] = React.useState(false);
  const router = useRouter();
  const pathname = usePathname();
  React.useEffect(() => { if (open) setOpen(false); }, [pathname]);
  const onComplete = (data: { countries?: string[]; cpu?: number; memory?: number; storage?: number; sshKeyId?: string; max_usd_per_month?: number; provider_id?: string }) => {
    try {
      localStorage.setItem('requestor_pending_create', JSON.stringify(data));
      if (data.provider_id) localStorage.setItem('requestor_pending_rent', data.provider_id);
    } catch {}
    setOpen(false);
    router.push('/providers');
  };
  return (
    <>
      <header className="sticky top-0 z-20 w-full border-b bg-white/80 backdrop-blur">
        <div className="flex w-full items-center justify-between px-3 sm:px-4 py-3">
          <div className="flex items-center gap-2 lg:hidden">
            <div className="size-6 rounded-lg bg-gradient-to-tr from-brand-600 to-brand-400" />
            <span className="font-semibold">Golem Requestor</span>
          </div>
          <div className="ml-auto flex items-center gap-3">
            {busy && <Spinner className="h-4 w-4" />}
            <button className="btn btn-primary" onClick={() => setOpen(true)}>Rent a VM</button>
            <WalletStatus />
          </div>
        </div>
      </header>
      <CreateWizard open={open} onClose={() => setOpen(false)} onComplete={onComplete} />
    </>
  );
}

function WalletStatus() {
  const { isInstalled, isConnected, account, chainId, connect } = useWallet();
  if (!isInstalled) {
    return (
      <button className="btn btn-secondary" onClick={() => alert('MetaMask not detected')}>No MetaMask</button>
    );
  }
  if (!isConnected) {
    return (
      <button className="btn btn-secondary" onClick={connect}>Connect MetaMask</button>
    );
  }
  return (
    <span className="inline-flex items-center rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm">
      {account?.slice(0, 6)}…{account?.slice(-4)} {chainId ? `· ${chainId}` : ''}
    </span>
  );
}
