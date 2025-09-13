"use client";
import React from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { loadRentals, saveRentals, vmStop, vmDestroy, loadSettings, type Rental } from "../../lib/api";
import { useAds } from "../../context/AdsContext";
import { useToast } from "../../components/ui/Toast";
import { Spinner } from "../../components/ui/Spinner";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { Skeleton } from "../../components/ui/Skeleton";
import { BrowserProvider, Contract } from "ethers";
import streamPayment from "../../public/abi/StreamPayment.json";
import { useStreamActions } from "../../hooks/useStreamActions";
import { useWallet } from "../../context/WalletContext";
import { buildSshCommand } from "../../lib/ssh";
import { humanDuration, type ChainStream, fetchStreamWithMeta } from "../../lib/streams";
import { parseHumanDuration } from "../../lib/time";
import { getPriceUSD, onPricesUpdated } from "../../lib/prices";
import { RiCpuLine, RiStackLine, RiHardDrive2Line } from "@remixicon/react";
import { StreamCard } from "../../components/streams/StreamCard";
import { countryFlagEmoji, countryFullName } from "../../lib/intl";
import { useProviderInfo, useVmAccess, useVmStatusSafe, useVmStatus } from "../../hooks/useApiSWR";

// ChainStream imported from lib/streams

// StatusBadge imported from shared UI

// Country helpers imported from lib/intl

// humanDuration provided by lib/streams

const parseTimeInput = parseHumanDuration;

export default function VmDetailsClient() {
  const search = useSearchParams();
  const router = useRouter();
  const { ads } = useAds();
  const { show } = useToast();
  const [mounted, setMounted] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  const [access, setAccess] = React.useState<{ ssh_port?: number } | null>(null);
  const [stream, setStream] = React.useState<{ chain: ChainStream; remaining: bigint } | null>(null);
  const [remaining, setRemaining] = React.useState<number>(0);
  const [err, setErr] = React.useState<string | null>(null);
  const { account } = useWallet();
  const [provider, setProvider] = React.useState<{ country?: string | null; platform?: string | null; ip_address?: string | null } | null>(null);
  const [tokenSymbol, setTokenSymbol] = React.useState<string>('');
  const [tokenDecimals, setTokenDecimals] = React.useState<number>(18);
  const [usdPrice, setUsdPrice] = React.useState<number | null>(null);
  const [customTopup, setCustomTopup] = React.useState<string>("");
  const [displayCurrency, setDisplayCurrency] = React.useState<'fiat'|'token'>(loadSettings().display_currency === 'token' ? 'token' : 'fiat');

  const vmId = search.get('id') || '';
  const [vm, setVm] = React.useState<ReturnType<typeof loadRentals>[number] | null>(null);

  const spAddr = (loadSettings().stream_payment_address || process.env.NEXT_PUBLIC_STREAM_PAYMENT_ADDRESS || '').trim();

  React.useEffect(() => { setMounted(true); }, []);
  // React to Settings changes (currency toggle) live
  React.useEffect(() => {
    const onSettings = (e: any) => {
      try { setDisplayCurrency(e?.detail?.display_currency === 'token' ? 'token' : 'fiat'); } catch {}
    };
    const onStorage = () => setDisplayCurrency(loadSettings().display_currency === 'token' ? 'token' : 'fiat');
    window.addEventListener('requestor_settings_changed', onSettings as any);
    window.addEventListener('storage', onStorage);
    return () => {
      window.removeEventListener('requestor_settings_changed', onSettings as any);
      window.removeEventListener('storage', onStorage);
    };
  }, []);

  // Resolve VM from local storage after mount to avoid SSR hydration mismatches
  React.useEffect(() => {
    try {
      const list = loadRentals();
      const rec = list.find(r => r.vm_id === vmId) || null;
      setVm(rec as any);
    } catch { setVm(null); }
  }, [vmId]);

  // SWR-backed provider info, access, and VM existence polling
  const { data: swrProvider } = useProviderInfo(vm?.provider_id, { refreshInterval: 30000 });
  const { data: swrAccess } = useVmAccess(vm?.provider_id, vm?.vm_id, { refreshInterval: 8000 });
  const { data: swrStatus } = useVmStatusSafe(vm?.provider_id, vm?.vm_id, { refreshInterval: 8000 });
  const { data: swrVm } = useVmStatus(vm?.provider_id, vm?.vm_id, { refreshInterval: 8000 });

  React.useEffect(() => {
    if (swrProvider) setProvider({ country: (swrProvider as any).country, platform: (swrProvider as any).platform, ip_address: (swrProvider as any).ip_address });
  }, [swrProvider]);

  React.useEffect(() => {
    if (swrAccess) setAccess(swrAccess as any);
  }, [swrAccess]);

  // Reconcile local VM record with provider's authoritative status
  React.useEffect(() => {
    if (!vm || !swrVm) return;
    const s = (swrVm as any) || {};
    const status = String(s.status || '').toLowerCase();
    const sshPort = s.ssh_port != null ? Number(s.ssh_port) : null;
    const ipAddr = s.ip_address || null;
    const nowSec = Math.floor(Date.now()/1000);
    let next: any | null = null;
    if (status === 'running') {
      if (vm.status !== 'running' || vm.ssh_port !== sshPort || vm.provider_ip !== ipAddr) {
        next = { ...vm, status: 'running', ssh_port: sshPort, provider_ip: ipAddr };
      }
    } else if (status === 'stopped') {
      if (vm.status !== 'stopped') {
        next = { ...vm, status: 'stopped' };
      }
    } else if (status === 'terminated' || status === 'deleted') {
      if (vm.status !== 'terminated') {
        next = { ...vm, status: 'terminated', ssh_port: null, ended_at: nowSec };
      }
    }
    if (next) {
      try {
        const list = loadRentals();
        const idx = list.findIndex(x => x.vm_id === vm.vm_id && x.provider_id === vm.provider_id);
        if (idx >= 0) {
          const out = [...list];
          out[idx] = next as any;
          saveRentals(out);
        }
        setVm(next);
      } catch {
        setVm(next);
      }
    }
  }, [swrVm, vm?.vm_id, vm?.provider_id]);

  React.useEffect(() => {
    if (!vm || !swrStatus) return;
    const safe = swrStatus as any;
    if (!safe.exists && safe.code === 404) {
      setAccess(null);
      setProvider(prev => prev ? { ...prev } : prev);
      const createdAt = (vm as any).created_at ? Number((vm as any).created_at) : 0;
      const ageSec = createdAt ? Math.floor(Date.now()/1000) - createdAt : Infinity;
      const isCreating = ((vm.status || '').toLowerCase() === 'creating');
      const withinGrace = isCreating && ageSec < 180; // 3 minutes
      if (!withinGrace) {
        try {
          const list = loadRentals();
          const idx = list.findIndex(x => x.vm_id === vm.vm_id && x.provider_id === vm.provider_id);
          if (idx >= 0) {
            const next: Rental = { ...list[idx], status: 'terminated', ssh_port: null, ended_at: Math.floor(Date.now()/1000) };
            const out = [...list];
            out[idx] = next;
            saveRentals(out);
            setVm(next);
          }
        } catch {}
      }
    } else {
      const s = (safe as any).data;
      if (s?.resources) {
        setProvider(prev => ({ ...(prev || {}), resources: s.resources } as any));
      }
    }
  }, [swrStatus, vm?.vm_id, vm?.provider_id]);

  // Stream details via lightweight polling + local 1s countdown
  React.useEffect(() => {
    let cancelled = false;
    const run = async () => {
      if (!vm?.stream_id || !spAddr) { if (!cancelled) setStream(null); return; }
      try {
        const res = await fetchStreamWithMeta(spAddr, BigInt(vm.stream_id));
        if (cancelled) return;
        setStream({ chain: res.chain as any, remaining: BigInt(res.remaining) });
        setRemaining(Number(res.remaining));
        setTokenSymbol(String(res.tokenSymbol || 'ETH'));
        setTokenDecimals(Number(res.tokenDecimals || 18));
        setUsdPrice(res.usdPrice ?? null);
      } catch {
        if (!cancelled) setStream(null);
      }
    };
    run();
    const iv = setInterval(run, 15000);
    return () => { cancelled = true; clearInterval(iv); };
  }, [vm?.stream_id, spAddr]);

  // Keep USD price in sync with global cache
  React.useEffect(() => {
    const addr = (stream?.chain?.token || '').toLowerCase();
    if (!addr && !tokenSymbol) return;
    const glm = (loadSettings().glm_token_address || process.env.NEXT_PUBLIC_GLM_TOKEN_ADDRESS || '').toLowerCase();
    const symUpper = (typeof tokenSymbol === 'string' ? tokenSymbol : '').toUpperCase();
    const isEthLike = (addr === '0x0000000000000000000000000000000000000000') || symUpper === 'ETH' || symUpper === 'WETH';
    const isGlmLike = (glm && addr === glm) || symUpper === 'GLM';
    const pick = () => (isEthLike ? getPriceUSD('ETH') : (isGlmLike ? getPriceUSD('GLM') : null));
    setUsdPrice(pick());
    const off = onPricesUpdated(() => setUsdPrice(pick()));
    return () => { try { off && off(); } catch {} };
  }, [stream?.chain?.token, tokenSymbol]);

  // Countdown ticker for remaining seconds
  React.useEffect(() => {
    if (!stream) return;
    let t: any;
    t = setInterval(() => {
      setRemaining((x) => (x > 0 ? x - 1 : 0));
    }, 1000);
    return () => clearInterval(t);
  }, [stream?.chain?.stopTime]);

  if (!mounted) {
    // Full-page skeleton to align with Suspense fallback and prevent hydration mismatch
    return (
      <div className="space-y-6">
        <div className="card"><div className="card-body">
          <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <Skeleton className="h-5 w-24" />
                <Skeleton className="h-7 w-40" />
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-2">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-4 w-16" />
                <Skeleton className="h-4 w-24" />
              </div>
            </div>
            <div className="flex flex-col items-start gap-2 sm:items-end">
              <Skeleton className="h-4 w-40" />
              <div className="flex gap-2">
                <Skeleton className="h-9 w-24" />
                <Skeleton className="h-9 w-24" />
                <Skeleton className="h-9 w-24" />
              </div>
            </div>
          </div>
        </div></div>
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="card"><div className="card-body"><Skeleton className="h-6 w-24" /></div></div>
          <div className="card"><div className="card-body"><Skeleton className="h-6 w-24" /></div></div>
          <div className="card"><div className="card-body"><Skeleton className="h-6 w-24" /></div></div>
        </div>
        <div className="card"><div className="card-body">
          <div className="grid gap-6 sm:grid-cols-2">
            <div className="grid gap-3">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-4 w-48" />
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-4 w-28" />
              <Skeleton className="h-4 w-20" />
            </div>
            <div className="grid gap-3 content-start">
              <Skeleton className="h-4 w-32" />
              <div className="flex gap-2">
                <Skeleton className="h-9 w-20" />
                <Skeleton className="h-9 w-20" />
                <Skeleton className="h-9 w-20" />
              </div>
              <div className="flex items-center gap-2">
                <Skeleton className="h-9 w-full" />
                <Skeleton className="h-9 w-16" />
              </div>
            </div>
          </div>
        </div></div>
      </div>
    );
  }

  if (!vm) {
    return (
      <div className="space-y-4">
        <div className="text-red-600">VM not found in your rentals.</div>
        <button className="btn btn-secondary" onClick={() => router.push('/rentals')}>Back to Servers</button>
      </div>
    );
  }

  const sshHost = provider?.ip_address || vm.provider_ip || 'PROVIDER_IP';
  const sshPort = access?.ssh_port || (swrVm as any)?.ssh_port || vm.ssh_port || null;
  const sshCmd = sshPort ? buildSshCommand(sshHost, Number(sshPort)) : null;

  const copySSH = async () => {
    try {
      if (vm?.status === 'terminated') { show("VM has been terminated by provider"); return; }
      if (!sshCmd) { show("SSH port unavailable"); return; }
      await navigator.clipboard.writeText(sshCmd);
      show("SSH command copied");
    } catch { show("Could not copy SSH command"); }
  };

  const stopVm = async () => {
    if (vm.status === 'terminated') { show("VM already terminated"); return; }
    try { setBusy(true); await vmStop(vm.provider_id, vm.vm_id, ads); show("Stop requested"); }
    catch (e) { show("Stop failed"); }
    finally { setBusy(false); }
  };
  const destroyVm = async () => {
    if (!confirm('Destroy VM?')) return;
    try {
      setBusy(true);
      try {
        await vmDestroy(vm.provider_id, vm.vm_id, ads);
      } catch (e) {
        // Treat 404 as already deleted on provider; proceed to remove locally
      }
      // Remove locally
      try {
        const list = loadRentals();
        const left = list.filter(x => !(x.vm_id === vm.vm_id && x.provider_id === vm.provider_id));
        saveRentals(left);
      } catch {}
      show("Destroyed");
      router.push('/rentals');
    }
    catch (e) { show("Destroy failed"); setBusy(false); }
  };

  const { topUp: topUpAction } = useStreamActions(spAddr);
  const topUp = async (seconds: number) => {
    if (!vm.stream_id || !stream || !spAddr) return;
    try {
      setBusy(true);
      await topUpAction(BigInt(vm.stream_id), stream.chain.token, stream.chain.ratePerSecond, seconds);
      show("Top-up sent");
      // refresh stream
      const { ethereum } = window as any;
      const provider = new BrowserProvider(ethereum);
      const contract = new Contract(spAddr, (streamPayment as any).abi, provider);
      const res = (await contract.streams(BigInt(vm.stream_id))) as ChainStream;
      const now = BigInt((await provider.getBlock("latest"))!.timestamp!);
      const remaining = res.stopTime > now ? (res.stopTime - now) : 0n;
      setStream({ chain: res, remaining });
      setRemaining(Number(remaining));
    } catch (e) {
      show("Top-up failed");
    } finally { setBusy(false); }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="card">
        <div className="card-body">
          <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <StatusBadge status={((swrVm as any)?.status || vm.status || (sshPort ? 'running' : 'creating'))} />
                <h2 className="truncate">{vm.name}</h2>
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-gray-600">
                <div className="flex items-center gap-1"><span className="font-mono">{vm.vm_id}</span></div>
                <span>•</span>
                {(!mounted || provider === null) ? (
                  <div className="flex items-center gap-2">
                    <Skeleton className="h-4 w-6" />
                    <Skeleton className="h-4 w-32" />
                    <span>•</span>
                    <Skeleton className="h-4 w-16" />
                  </div>
                ) : (
                  <>
                    <div className="flex items-center gap-1">
                      <span className="text-lg leading-none">{provider?.country ? countryFlagEmoji(provider.country) : '🏳️'}</span>
                      <span>{provider?.country ? countryFullName(provider.country) : 'Unknown region'}</span>
                    </div>
                    {provider?.platform && (
                      <>
                        <span>•</span>
                        <span className="rounded border px-1.5 py-0.5 text-[11px] text-gray-700" title="Architecture">{provider.platform}</span>
                      </>
                    )}
                  </>
                )}
                <span>•</span>
                <div className="font-mono text-xs sm:text-sm">{vm.provider_id}</div>
              </div>
            </div>
            <div className="flex flex-col items-start gap-2 sm:items-end">
              <div className="text-sm text-gray-700">
                {(!mounted || access === null) ? (
                  <div className="flex items-center gap-2"><Skeleton className="h-4 w-36" /></div>
                ) : (
                  <>SSH: {sshHost}:{sshPort ?? '—'}</>
                )}
              </div>
              <div className="flex gap-2">
                <button className="btn btn-secondary" onClick={copySSH} disabled={!sshCmd || vm.status === 'terminated'}>Copy SSH</button>
                <button className="btn btn-secondary" onClick={stopVm} disabled={busy || vm.status === 'terminated'}>{busy ? <><Spinner className="h-4 w-4" /> Stop</> : 'Stop'}</button>
                <button className="btn btn-danger" onClick={destroyVm} disabled={busy}>Destroy</button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Specs */}
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="card"><div className="card-body">
          <div className="text-sm text-gray-500 inline-flex items-center gap-1.5"><RiCpuLine className="h-4 w-4 text-gray-500" /> CPU</div>
          <div className="mt-1 text-lg font-semibold">
            {(!mounted || provider === null || !(provider as any)?.resources?.cpu) ? (<Skeleton className="h-6 w-24" />) : (<>{(provider as any)?.resources?.cpu} vCPU</>)}
          </div>
        </div></div>
        <div className="card"><div className="card-body">
          <div className="text-sm text-gray-500 inline-flex items-center gap-1.5"><RiStackLine className="h-4 w-4 text-gray-500" /> Memory</div>
          <div className="mt-1 text-lg font-semibold">
            {(!mounted || provider === null || !(provider as any)?.resources?.memory) ? (<Skeleton className="h-6 w-24" />) : (<>{(provider as any)?.resources?.memory} GB</>)}
          </div>
        </div></div>
        <div className="card"><div className="card-body">
          <div className="text-sm text-gray-500 inline-flex items-center gap-1.5"><RiHardDrive2Line className="h-4 w-4 text-gray-500" /> Storage</div>
          <div className="mt-1 text-lg font-semibold">
            {(!mounted || provider === null || !(provider as any)?.resources?.storage) ? (<Skeleton className="h-6 w-24" />) : (<>{(provider as any)?.resources?.storage} GB</>)}
          </div>
        </div></div>
      </div>

      {/* Stream section via shared component */}
      {!vm.stream_id ? (
        <div className="card"><div className="card-body"><div className="text-sm text-gray-600">No stream mapped for this VM.</div></div></div>
      ) : (!mounted || !stream) ? (
        <div className="card"><div className="card-body">
          <div className="grid gap-6 sm:grid-cols-2">
            <div className="grid gap-3">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-4 w-48" />
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-4 w-28" />
              <Skeleton className="h-4 w-20" />
            </div>
            <div className="grid gap-3 content-start">
              <Skeleton className="h-4 w-32" />
              <div className="flex gap-2">
                <Skeleton className="h-9 w-20" />
                <Skeleton className="h-9 w-20" />
                <Skeleton className="h-9 w-20" />
              </div>
              <div className="flex items-center gap-2">
                <Skeleton className="h-9 w-full" />
                <Skeleton className="h-9 w-16" />
              </div>
            </div>
          </div>
        </div></div>
      ) : (
        <StreamCard
          title={`Stream`}
          streamId={vm.stream_id}
          chain={stream.chain as any}
          remaining={remaining}
          meta={{ tokenSymbol, tokenDecimals, usdPrice }}
          displayCurrency={displayCurrency}
          onTopUp={(secs) => topUp(secs)}
          busy={busy}
        />
      )}
    </div>
  );
}
