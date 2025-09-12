"use client";
import React from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { loadRentals, saveRentals, vmAccess, vmStop, vmDestroy, loadSettings, providerInfo as fetchProviderInfo, vmStatus, vmStatusSafe, type Rental } from "../../lib/api";
import { useAds } from "../../context/AdsContext";
import { useToast } from "../../components/ui/Toast";
import { Spinner } from "../../components/ui/Spinner";
import { Skeleton } from "../../components/ui/Skeleton";
import { BrowserProvider, Contract } from "ethers";
import streamPayment from "../../public/abi/StreamPayment.json";
import erc20 from "../../public/abi/ERC20.json";
import { ensureNetwork, getPaymentsChain } from "../../lib/chain";
import { useWallet } from "../../context/WalletContext";
import { buildSshCommand } from "../../lib/ssh";
import { humanDuration } from "../../lib/streams";
import { StreamCard } from "../../components/streams/StreamCard";

type ChainStream = {
  token: string; sender: string; recipient: string;
  startTime: bigint; stopTime: bigint; ratePerSecond: bigint;
  deposit: bigint; withdrawn: bigint; halted: boolean;
};

function StatusBadge({ status }: { status?: string | null }) {
  const s = (status || '').toLowerCase();
  if (s === 'running') return <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">● Running</span>;
  if (s === 'creating') return <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700"><Spinner className="h-3.5 w-3.5" /> Creating</span>;
  if (s === 'stopped') return <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-700">● Stopped</span>;
  if (s === 'terminated' || s === 'deleted') return <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">● Terminated</span>;
  if (s === 'error' || s === 'failed') return <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">● Error</span>;
  return <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700">● Unknown</span>;
}

function countryFlagEmoji(code: string): string {
  const cc = (code || '').toUpperCase();
  if (cc.length !== 2) return '🏳️';
  const A = 0x1F1E6;
  const alpha = 'A'.charCodeAt(0);
  return Array.from(cc).map(ch => String.fromCodePoint(A + (ch.charCodeAt(0) - alpha))).join('');
}

function countryFullName(code: string): string {
  try {
    // @ts-ignore
    const dn = new Intl.DisplayNames(['en'], { type: 'region' });
    return dn.of((code || '').toUpperCase()) || (code || '').toUpperCase();
  } catch { return (code || '').toUpperCase(); }
}

// humanDuration provided by lib/streams

function parseTimeInput(v: string): number | null {
  // Accept inputs like "90", "30m", "2h", "1h 30m", "2h 30m 20s"
  if (!v) return null;
  const t = v.trim().toLowerCase();
  if (!t.length) return null;
  if (/^\d+$/.test(t)) return parseInt(t, 10) * 60; // minutes
  let seconds = 0;
  const re = /(\d+)\s*(h|m|s)/g;
  let m;
  while ((m = re.exec(t))) {
    const n = parseInt(m[1], 10);
    const u = m[2];
    if (u === 'h') seconds += n * 3600; else if (u === 'm') seconds += n * 60; else seconds += n;
  }
  return seconds || null;
}

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
  const displayCurrency = (loadSettings().display_currency === 'token' ? 'token' : 'fiat');

  const vmId = search.get('id') || '';
  const [vm, setVm] = React.useState<ReturnType<typeof loadRentals>[number] | null>(null);

  const spAddr = (loadSettings().stream_payment_address || process.env.NEXT_PUBLIC_STREAM_PAYMENT_ADDRESS || '').trim();

  React.useEffect(() => { setMounted(true); }, []);

  // Resolve VM from local storage after mount to avoid SSR hydration mismatches
  React.useEffect(() => {
    try {
      const list = loadRentals();
      const rec = list.find(r => r.vm_id === vmId) || null;
      setVm(rec as any);
    } catch { setVm(null); }
  }, [vmId]);

  React.useEffect(() => {
    if (!vm) return;
    (async () => {
      try {
        setErr(null);
        const acc = await vmAccess(vm.provider_id, vm.vm_id, ads).catch(() => ({}));
        setAccess(acc);
      } catch {}
      try {
        const p = await fetchProviderInfo(vm.provider_id, ads).catch(() => null);
        if (p) setProvider({ country: p.country, platform: p.platform, ip_address: p.ip_address });
      } catch {}
      try {
        // If VM no longer exists, mark rental as terminated locally
        const safe = await vmStatusSafe(vm.provider_id, vm.vm_id, ads);
        if (!safe.exists && safe.code === 404) {
          setAccess(null);
          setProvider(prev => prev ? { ...prev } : prev);
          // Update local rental record to reflect termination
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
        } else {
          const s = safe.data;
          if (s?.resources) {
            // Attach resources to displayed provider specs
            setProvider(prev => ({ ...(prev || {}), resources: s.resources } as any));
          }
        }
      } catch {}
      try {
        if (vm.stream_id && spAddr) {
          const { ethereum } = window as any;
          const provider = new BrowserProvider(ethereum);
          const contract = new Contract(spAddr, (streamPayment as any).abi, provider);
          const res = (await contract.streams(BigInt(vm.stream_id))) as ChainStream;
          const now = BigInt((await provider.getBlock("latest"))!.timestamp!);
          const remaining = res.stopTime > now ? (res.stopTime - now) : 0n;
          setStream({ chain: res, remaining });
          setRemaining(Number(remaining));
          // Token meta
          const zero = '0x0000000000000000000000000000000000000000';
          if (res.token && res.token.toLowerCase() !== zero) {
            try {
              const erc = new Contract(res.token, (erc20 as any).abi, provider);
              const [sym, dec] = await Promise.all([
                erc.symbol().catch(() => 'TOKEN'),
                erc.decimals().catch(() => 18),
              ]);
              setTokenSymbol(String(sym || 'TOKEN'));
              setTokenDecimals(Number(dec || 18));
            } catch {
              setTokenSymbol('TOKEN'); setTokenDecimals(18);
            }
          } else {
            setTokenSymbol('ETH'); setTokenDecimals(18);
          }
          // USD price (best-effort)
          try {
            let price: number | null = null;
            const addr = (res.token || '').toLowerCase();
            const glm = (loadSettings().glm_token_address || process.env.NEXT_PUBLIC_GLM_TOKEN_ADDRESS || '').toLowerCase();
            if (addr === '0x0000000000000000000000000000000000000000') {
              // Native ETH
              const r = await fetch('https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd');
              const js = await r.json().catch(() => ({}));
              price = js?.ethereum?.usd ?? null;
            } else if (glm && addr === glm) {
              const r = await fetch('https://api.coingecko.com/api/v3/simple/price?ids=golem&vs_currencies=usd');
              const js = await r.json().catch(() => ({}));
              price = js?.golem?.usd ?? null;
            }
            setUsdPrice(price);
          } catch { setUsdPrice(null); }
        } else {
          setStream(null);
        }
      } catch (e: any) {
        setStream(null);
      }
    })();
  // Re-run when VM context is available or changes
  }, [vm?.vm_id, vm?.provider_id, vm?.stream_id, ads, spAddr]);

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
  const sshPort = access?.ssh_port || vm.ssh_port || null;
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

  const topUp = async (seconds: number) => {
    if (!vm.stream_id || !stream || !spAddr) return;
    try {
      setBusy(true);
      const { ethereum } = window as any;
      await ensureNetwork(ethereum, getPaymentsChain());
      const provider = new BrowserProvider(ethereum);
      const signer = await provider.getSigner(account ?? undefined);
      const contract = new Contract(spAddr, (streamPayment as any).abi, signer);
      const addWei = stream.chain.ratePerSecond * BigInt(seconds);
      const tx = await contract.topUp(BigInt(vm.stream_id), addWei, {
        value: stream.chain.token === '0x0000000000000000000000000000000000000000' ? addWei : 0n,
        gasLimit: 150000n,
      });
      await tx.wait();
      show("Top-up sent");
      // refresh stream
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
                <StatusBadge status={vm.status || (vm.ssh_port ? 'running' : 'creating')} />
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
                    {provider?.platform && (<><span>•</span><div>{provider.platform}</div></>)}
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
          <div className="text-sm text-gray-500">CPU</div>
          <div className="mt-1 text-lg font-semibold">
            {(!mounted || provider === null || !(provider as any)?.resources?.cpu) ? (<Skeleton className="h-6 w-24" />) : (<>{(provider as any)?.resources?.cpu} vCPU</>)}
          </div>
        </div></div>
        <div className="card"><div className="card-body">
          <div className="text-sm text-gray-500">Memory</div>
          <div className="mt-1 text-lg font-semibold">
            {(!mounted || provider === null || !(provider as any)?.resources?.memory) ? (<Skeleton className="h-6 w-24" />) : (<>{(provider as any)?.resources?.memory} GB</>)}
          </div>
        </div></div>
        <div className="card"><div className="card-body">
          <div className="text-sm text-gray-500">Storage</div>
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
