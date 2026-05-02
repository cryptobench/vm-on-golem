"use client";
import React from "react";
import { useSearchParams, useRouter } from "next/navigation";
import {
  loadRentals,
  saveRentals,
  createSnapshot,
  deleteSnapshot,
  listSnapshots,
  restoreSnapshot,
  vmDestroy,
  vmRestart,
  vmResume,
  vmResize,
  vmStart,
  vmStop,
  vmSuspend,
  loadSettings,
  type Rental,
} from "../../lib/api";
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
import { RiCpuLine, RiStackLine, RiHardDrive2Line, RiFileCopyLine } from "@remixicon/react";
import { StreamCard } from "../../components/streams/StreamCard";
import { countryFlagEmoji, countryFullName } from "../../lib/intl";
import { useProviderInfo, useVmAccess, useVmStatusSafe, useVmStatus, useVmMetricsLatest } from "../../hooks/useApiSWR";
import { ConfirmDialog } from "../../components/ui/ConfirmDialog";

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
  const [snapshots, setSnapshots] = React.useState<Array<{ name: string; comment?: string | null; created_at?: string | null }>>([]);
  const [snapshotName, setSnapshotName] = React.useState("");
  const [snapshotBusy, setSnapshotBusy] = React.useState<string | null>(null);
  const [resizeCpu, setResizeCpu] = React.useState<number>(1);
  const [resizeMemory, setResizeMemory] = React.useState<number>(1);
  const [resizeStorage, setResizeStorage] = React.useState<number>(10);

  const vmId = search.get('id') || '';
  const [vm, setVm] = React.useState<ReturnType<typeof loadRentals>[number] | null>(null);

  const spAddr = (loadSettings().stream_payment_address || process.env.NEXT_PUBLIC_STREAM_PAYMENT_ADDRESS || '').trim();

  // Destroy confirmation state (must be before any early returns)
  const [confirmDestroyOpen, setConfirmDestroyOpen] = React.useState(false);
  const openDestroy = () => setConfirmDestroyOpen(true);
  const closeDestroy = () => setConfirmDestroyOpen(false);

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
  const { data: swrMetrics, isLoading: metricsLoading } = useVmMetricsLatest(vm?.provider_id, vm?.vm_id, { refreshInterval: 10000 });

  React.useEffect(() => {
    if (swrProvider) setProvider({ country: (swrProvider as any).country, platform: (swrProvider as any).platform, ip_address: (swrProvider as any).ip_address });
  }, [swrProvider]);

  React.useEffect(() => {
    if (swrAccess) setAccess(swrAccess as any);
  }, [swrAccess]);

  // Reconcile local VM record with provider's authoritative status (full status endpoint)
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

  // Safe status endpoint: handle 404 termination and enrich provider resources.
  // Also reconcile status when full endpoint data is unavailable.
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
      const s = (safe as any).data || {};
      // Update provider resources if present
      if (s?.resources) {
        setProvider(prev => ({ ...(prev || {}), resources: s.resources } as any));
      }
      // If we have status in the safe payload and it differs locally, reconcile.
      if (s && s.status) {
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

  React.useEffect(() => {
    if (!vm) return;
    listSnapshots(vm.provider_id, vm.vm_id, ads)
      .then((rows) => setSnapshots(Array.isArray(rows) ? rows : []))
      .catch(() => setSnapshots([]));
  }, [vm?.provider_id, vm?.vm_id, vm?.status, ads]);

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
        <button className="btn btn-secondary" onClick={() => router.push('/rentals')}>Back to VMs</button>
      </div>
    );
  }

  const sshHost = provider?.ip_address || vm.provider_ip || 'PROVIDER_IP';
  const sshPort = access?.ssh_port || (swrVm as any)?.ssh_port || vm.ssh_port || null;
  const sshCmd = sshPort ? buildSshCommand(sshHost, Number(sshPort)) : null;
  const effectiveStatus = String((swrVm as any)?.status || (swrStatus as any)?.data?.status || vm.status || '').toLowerCase();
  const isStopped = effectiveStatus === 'stopped';
  const isSuspended = effectiveStatus === 'suspended' || effectiveStatus === 'suspending';
  const isRunning = effectiveStatus === 'running';
  const isTerminated = effectiveStatus === 'terminated' || effectiveStatus === 'deleted';

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
    try { setBusy(true); await vmStop(vm.provider_id, vm.vm_id, ads); updateVmStatus("stopped"); show("Stop requested"); }
    catch (e) { show("Stop failed"); }
    finally { setBusy(false); }
  };
  const startVm = async () => {
    if (vm.status === 'terminated') { show("VM already terminated"); return; }
    try { setBusy(true); await vmStart(vm.provider_id, vm.vm_id, ads); updateVmStatus("running"); show("Start requested"); }
    catch (e) { show("Start failed"); }
    finally { setBusy(false); }
  };
  const restartVm = async () => {
    if (vm.status === 'terminated') { show("VM already terminated"); return; }
    try { setBusy(true); await vmRestart(vm.provider_id, vm.vm_id, ads); updateVmStatus("running"); show("Restart requested"); }
    catch (e) { show("Restart failed"); }
    finally { setBusy(false); }
  };
  const suspendVm = async () => {
    if (vm.status === 'terminated') { show("VM already terminated"); return; }
    try { setBusy(true); await vmSuspend(vm.provider_id, vm.vm_id, ads); updateVmStatus("suspended"); show("Suspend requested"); }
    catch (e) { show("Suspend failed"); }
    finally { setBusy(false); }
  };
  const resumeVm = async () => {
    if (vm.status === 'terminated') { show("VM already terminated"); return; }
    try { setBusy(true); await vmResume(vm.provider_id, vm.vm_id, ads); updateVmStatus("running"); show("Resume requested"); }
    catch (e) { show("Resume failed"); }
    finally { setBusy(false); }
  };
  const updateVmStatus = (status: string) => {
    const next = { ...vm, status } as Rental;
    try {
      const list = loadRentals();
      const idx = list.findIndex(x => x.vm_id === vm.vm_id && x.provider_id === vm.provider_id);
      if (idx >= 0) {
        const out = [...list];
        out[idx] = next;
        saveRentals(out);
      }
    } catch {}
    setVm(next as any);
  };
  const refreshSnapshots = async () => {
    const rows = await listSnapshots(vm.provider_id, vm.vm_id, ads);
    setSnapshots(Array.isArray(rows) ? rows : []);
  };
  const createVmSnapshot = async () => {
    try {
      setSnapshotBusy("create");
      await createSnapshot(
        vm.provider_id,
        vm.vm_id,
        { name: snapshotName.trim() || undefined },
        ads,
      );
      setSnapshotName("");
      await refreshSnapshots();
      show("Snapshot created");
    } catch {
      show("Snapshot failed. Stop the VM first and try again.");
    } finally {
      setSnapshotBusy(null);
    }
  };
  const restoreVmSnapshot = async (name: string) => {
    try {
      setSnapshotBusy(`restore:${name}`);
      await restoreSnapshot(vm.provider_id, vm.vm_id, name, ads);
      await refreshSnapshots();
      show("Snapshot restored");
    } catch {
      show("Restore failed. Stop the VM first and try again.");
    } finally {
      setSnapshotBusy(null);
    }
  };
  const deleteVmSnapshot = async (name: string) => {
    try {
      setSnapshotBusy(`delete:${name}`);
      await deleteSnapshot(vm.provider_id, vm.vm_id, name, ads);
      await refreshSnapshots();
      show("Snapshot deleted");
    } catch {
      show("Delete snapshot failed");
    } finally {
      setSnapshotBusy(null);
    }
  };
  const resizeVm = async () => {
    try {
      setBusy(true);
      await vmResize(
        vm.provider_id,
        vm.vm_id,
        { cpu: resizeCpu, memory: resizeMemory, storage: resizeStorage },
        ads,
      );
      const next = { ...vm, resources: { cpu: resizeCpu, memory: resizeMemory, storage: resizeStorage } } as Rental;
      const list = loadRentals();
      const idx = list.findIndex(x => x.vm_id === vm.vm_id && x.provider_id === vm.provider_id);
      if (idx >= 0) {
        const out = [...list];
        out[idx] = next;
        saveRentals(out);
      }
      setVm(next as any);
      show("Resize applied");
    } catch {
      show("Resize failed. Stop the VM first and check capacity.");
    } finally {
      setBusy(false);
    }
  };
  const confirmDestroy = async () => {
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
      show("Terminated");
      closeDestroy();
      router.push('/rentals');
    }
    catch (e) { show("Terminate failed"); }
    finally { setBusy(false); }
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

  // Pick VM spec from provider status if exposed, else from saved rental (no hook to avoid order issues)
  const effectiveResources = (() => {
    const s = (swrVm as any) || {};
    const r = (s?.resources && typeof s.resources === 'object') ? s.resources : s;
    const cpu = Number((r as any)?.cpu);
    const memory = Number((r as any)?.memory);
    const storage = Number((r as any)?.storage);
    if ([cpu, memory, storage].every((n) => Number.isFinite(n) && n > 0)) return { cpu, memory, storage };
    return vm?.resources || null;
  })();

  const guestMetrics = (() => {
    const byVm = (swrMetrics as any)?.vms || {};
    return byVm[vm.vm_id]?.guest_agent || null;
  })();
  const metricPercent = (name: string) => {
    const value = Number(guestMetrics?.[name]?.value);
    return Number.isFinite(value) ? Math.max(0, Math.min(100, value)) : null;
  };
  const metricText = (name: string) => {
    const value = metricPercent(name);
    return value == null ? "—" : `${value.toFixed(0)}%`;
  };
  const metricsUpdatedAt = guestMetrics?.agent_heartbeat?.timestamp
    ? new Date(guestMetrics.agent_heartbeat.timestamp).toLocaleTimeString()
    : null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="card">
        <div className="card-body">
          <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <StatusBadge status={((swrVm as any)?.status || (swrStatus as any)?.data?.status || vm.status || (sshPort ? 'running' : 'creating'))} />
                <h2 className="truncate">{vm.name}</h2>
              </div>
              {/* Provider wallet (secondary label) */}
              <div className="mt-1 font-mono text-xs sm:text-sm text-gray-700 break-all" title="Provider wallet">
                {vm.provider_id}
              </div>
              {/* Country and architecture */}
              <div className="mt-1 text-sm text-gray-600">
                {(!mounted || provider === null) ? (
                  <div className="flex items-center gap-2">
                    <Skeleton className="h-4 w-6" />
                    <Skeleton className="h-4 w-32" />
                    <Skeleton className="h-4 w-16" />
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    <span className="text-lg leading-none">{provider?.country ? countryFlagEmoji(provider.country) : '🏳️'}</span>
                    <span>{provider?.country ? countryFullName(provider.country) : 'Unknown region'}</span>
                    {provider?.platform && (
                      <>
                        <span>•</span>
                        <span className="rounded border px-1.5 py-0.5 text-[11px] text-gray-700" title="Architecture">{provider.platform}</span>
                      </>
                    )}
                  </div>
                )}
              </div>
              {/* IP with copy icon */}
              <div className="mt-1 text-sm text-gray-700">
                {(!mounted || provider === null) ? (
                  <Skeleton className="h-4 w-40" />
                ) : (
                  (() => {
                    const ip = provider?.ip_address || vm.provider_ip || null;
                    const copy = async () => {
                      try {
                        if (!ip) { show('IP unavailable'); return; }
                        await navigator.clipboard.writeText(String(ip));
                        show('IP copied');
                      } catch { show('Could not copy IP'); }
                    };
                    return (
                      <div className="inline-flex items-center gap-1">
                        <button type="button" onClick={copy} className="font-mono text-sm text-gray-800 hover:underline" title="Copy IP">
                          {ip ? `${ip}` : '—'}
                        </button>
                        <button type="button" onClick={copy} className="text-gray-600 hover:text-gray-900" aria-label="Copy IP" title="Copy IP">
                          <RiFileCopyLine className="h-4 w-4" />
                        </button>
                      </div>
                    );
                  })()
                )}
              </div>
            </div>
            <div className="flex flex-col items-start gap-2 sm:items-end">
              <div className="flex gap-2">
                <button className="btn btn-secondary" onClick={copySSH} disabled={!sshCmd || isTerminated}>Copy SSH</button>
                {(isStopped || isSuspended) && (
                  <button className="btn btn-secondary" onClick={isSuspended ? resumeVm : startVm} disabled={busy || isTerminated}>
                    {busy ? <><Spinner className="h-4 w-4" /> {isSuspended ? 'Resume' : 'Start'}</> : (isSuspended ? 'Resume' : 'Start')}
                  </button>
                )}
                {isRunning && (
                  <>
                    <button className="btn btn-secondary" onClick={stopVm} disabled={busy || isTerminated}>
                      {busy ? <><Spinner className="h-4 w-4" /> Stop</> : 'Stop'}
                    </button>
                    <button className="btn btn-secondary" onClick={restartVm} disabled={busy || isTerminated}>
                      {busy ? <><Spinner className="h-4 w-4" /> Restart</> : 'Restart'}
                    </button>
                    <button className="btn btn-secondary" onClick={suspendVm} disabled={busy || isTerminated}>
                      {busy ? <><Spinner className="h-4 w-4" /> Suspend</> : 'Suspend'}
                    </button>
                  </>
                )}
                <button className="btn btn-danger" onClick={openDestroy} disabled={busy}>Terminate</button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Specs */}
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="card"><div className="card-body">
          <div className="text-sm text-gray-500 inline-flex items-center gap-1.5"><RiCpuLine className="h-4 w-4 text-gray-500" /> vCPU</div>
          <div className="mt-1 text-lg font-semibold">
            {(!mounted || !effectiveResources?.cpu) ? (<Skeleton className="h-6 w-24" />) : (<>{effectiveResources.cpu} vCPU</>)}
          </div>
        </div></div>
        <div className="card"><div className="card-body">
          <div className="text-sm text-gray-500 inline-flex items-center gap-1.5"><RiStackLine className="h-4 w-4 text-gray-500" /> RAM</div>
          <div className="mt-1 text-lg font-semibold">
            {(!mounted || !effectiveResources?.memory) ? (<Skeleton className="h-6 w-24" />) : (<>{effectiveResources.memory} GB</>)}
          </div>
        </div></div>
        <div className="card"><div className="card-body">
          <div className="text-sm text-gray-500 inline-flex items-center gap-1.5"><RiHardDrive2Line className="h-4 w-4 text-gray-500" /> Storage</div>
          <div className="mt-1 text-lg font-semibold">
            {(!mounted || !effectiveResources?.storage) ? (<Skeleton className="h-6 w-24" />) : (<>{effectiveResources.storage} GB</>)}
          </div>
        </div></div>
      </div>

      <div className="card">
        <div className="card-body">
          <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
            <h3>Live Metrics</h3>
            <div className="text-xs text-gray-500">
              {metricsUpdatedAt ? `Updated ${metricsUpdatedAt}` : "Guest metrics unavailable"}
            </div>
          </div>
          {metricsLoading ? (
            <div className="mt-4 grid gap-4 sm:grid-cols-3">
              <Skeleton className="h-20 w-full" />
              <Skeleton className="h-20 w-full" />
              <Skeleton className="h-20 w-full" />
            </div>
          ) : guestMetrics ? (
            <div className="mt-4 grid gap-4 sm:grid-cols-3">
              {[
                ["CPU", "cpu_percent"],
                ["RAM", "memory_percent"],
                ["Disk", "disk_percent"],
              ].map(([label, key]) => (
                <div key={key} className="border border-gray-200 p-3">
                  <div className="text-sm text-gray-500">{label}</div>
                  <div className="mt-1 text-xl font-semibold">{metricText(key)}</div>
                  <div className="mt-3 h-2 bg-gray-100">
                    <div className="h-2 bg-brand-600" style={{ width: `${metricPercent(key) || 0}%` }} />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="mt-4 border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
              Guest metrics are not available yet. The default VM agent only publishes metrics and does not give providers shell or file access.
            </div>
          )}
        </div>
      </div>

      <div className="card">
        <div className="card-body">
          <div className="grid gap-6 lg:grid-cols-2">
            <div>
              <div className="flex items-center justify-between gap-3">
                <h3>Snapshots</h3>
                <button className="btn btn-secondary" onClick={refreshSnapshots} disabled={!!snapshotBusy}>Refresh</button>
              </div>
              <div className="mt-3 flex flex-col gap-2 sm:flex-row">
                <input
                  className="input"
                  value={snapshotName}
                  onChange={(e) => setSnapshotName(e.target.value)}
                  placeholder="snapshot-name"
                  disabled={!!snapshotBusy || !isStopped}
                />
                <button className="btn btn-primary" onClick={createVmSnapshot} disabled={!!snapshotBusy || !isStopped}>
                  {snapshotBusy === 'create' ? <><Spinner className="h-4 w-4 text-white" /> Creating...</> : 'Create'}
                </button>
              </div>
              <div className="mt-4 divide-y divide-gray-100">
                {snapshots.length ? snapshots.map((snapshot) => (
                  <div key={snapshot.name} className="flex items-center justify-between gap-3 py-3">
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium text-gray-900">{snapshot.name}</div>
                      {snapshot.comment && <div className="truncate text-xs text-gray-500">{snapshot.comment}</div>}
                    </div>
                    <div className="flex gap-2">
                      <button className="btn btn-secondary" onClick={() => restoreVmSnapshot(snapshot.name)} disabled={!!snapshotBusy || !isStopped}>
                        {snapshotBusy === `restore:${snapshot.name}` ? <><Spinner className="h-4 w-4" /> Restore</> : 'Restore'}
                      </button>
                      <button className="btn btn-secondary" onClick={() => deleteVmSnapshot(snapshot.name)} disabled={!!snapshotBusy}>
                        {snapshotBusy === `delete:${snapshot.name}` ? <><Spinner className="h-4 w-4" /> Delete</> : 'Delete'}
                      </button>
                    </div>
                  </div>
                )) : (
                  <div className="py-3 text-sm text-gray-600">No snapshots.</div>
                )}
              </div>
            </div>
            <div>
              <h3>Resize</h3>
              <div className="mt-3 grid gap-3 sm:grid-cols-3">
                <div>
                  <label className="label">vCPU</label>
                  <input className="input" type="number" min={1} value={resizeCpu} onChange={(e) => setResizeCpu(Number(e.target.value))} disabled={!isStopped || busy} />
                </div>
                <div>
                  <label className="label">RAM GB</label>
                  <input className="input" type="number" min={1} value={resizeMemory} onChange={(e) => setResizeMemory(Number(e.target.value))} disabled={!isStopped || busy} />
                </div>
                <div>
                  <label className="label">Disk GB</label>
                  <input className="input" type="number" min={effectiveResources?.storage || 10} value={resizeStorage} onChange={(e) => setResizeStorage(Number(e.target.value))} disabled={!isStopped || busy} />
                </div>
              </div>
              <div className="mt-4 flex items-center justify-between gap-3">
                <div className="text-sm text-gray-600">Resize requires a stopped VM. Disk can only increase.</div>
                <button className="btn btn-primary" onClick={resizeVm} disabled={!isStopped || busy}>
                  {busy ? <><Spinner className="h-4 w-4 text-white" /> Applying...</> : 'Apply Resize'}
                </button>
              </div>
            </div>
          </div>
        </div>
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
      {/* Terminate confirmation modal */}
      <ConfirmDialog
        open={confirmDestroyOpen}
        onCancel={closeDestroy}
        onConfirm={confirmDestroy}
        title="Terminate VM"
        description="Are you sure you want to permanently terminate this VM? This action cannot be undone."
        confirmLabel="Terminate"
        danger
        busy={busy}
      />
    </div>
  );
}
