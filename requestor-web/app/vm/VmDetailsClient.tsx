"use client";
import React from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { loadRentals, vmAccess, vmStop, vmDestroy, loadSettings, providerInfo as fetchProviderInfo, vmStatus } from "../../lib/api";
import { useAds } from "../../context/AdsContext";
import { useToast } from "../../components/ui/Toast";
import { Spinner } from "../../components/ui/Spinner";
import { BrowserProvider, Contract } from "ethers";
import streamPayment from "../../public/abi/StreamPayment.json";
import erc20 from "../../public/abi/ERC20.json";
import { ensureNetwork, getPaymentsChain } from "../../lib/chain";
import { useWallet } from "../../context/WalletContext";

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

function humanDuration(totalSec: number): string {
  const s = Math.max(0, Math.floor(totalSec));
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  const parts: string[] = [];
  if (d) parts.push(`${d} day${d!==1?'s':''}`);
  if (h) parts.push(`${h} hour${h!==1?'s':''}`);
  if (m) parts.push(`${m} minute${m!==1?'s':''}`);
  if (sec && parts.length < 2) parts.push(`${sec} second${sec!==1?'s':''}`);
  return parts.length ? parts.join(', ') : '0 seconds';
}

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

  const rentals = loadRentals();
  const vmId = search.get('id') || '';
  const vm = rentals.find(r => r.vm_id === vmId);

  const spAddr = (loadSettings().stream_payment_address || process.env.NEXT_PUBLIC_STREAM_PAYMENT_ADDRESS || '').trim();

  React.useEffect(() => { setMounted(true); }, []);

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
        const s = await vmStatus(vm.provider_id, vm.vm_id, ads).catch(() => null);
        if (s?.resources) {
          // Attach resources to displayed provider specs
          setProvider(prev => ({ ...(prev || {}), resources: s.resources } as any));
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
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [vmId]);

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
    return <div className="text-sm text-gray-600">Loading VM…</div>;
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
  const keyPath = "~/.golem/requestor/ssh/golem_id_rsa";
  const sshCmd = sshPort ? `ssh -i ${keyPath} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p ${sshPort} ubuntu@${sshHost}` : null;

  const copySSH = async () => {
    try {
      if (!sshCmd) { show("SSH port unavailable"); return; }
      await navigator.clipboard.writeText(sshCmd);
      show("SSH command copied");
    } catch { show("Could not copy SSH command"); }
  };

  const stopVm = async () => {
    try { setBusy(true); await vmStop(vm.provider_id, vm.vm_id, ads); show("Stop requested"); }
    catch (e) { show("Stop failed"); }
    finally { setBusy(false); }
  };
  const destroyVm = async () => {
    if (!confirm('Destroy VM?')) return;
    try { setBusy(true); await vmDestroy(vm.provider_id, vm.vm_id, ads); show("Destroy requested"); router.push('/rentals'); }
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
                <div className="flex items-center gap-1">
                  <span className="text-lg leading-none">{provider?.country ? countryFlagEmoji(provider.country) : '🏳️'}</span>
                  <span>{provider?.country ? countryFullName(provider.country) : 'Unknown region'}</span>
                </div>
                {provider?.platform && (<><span>•</span><div>{provider.platform}</div></>)}
                <span>•</span>
                <div className="font-mono text-xs sm:text-sm">{vm.provider_id}</div>
              </div>
            </div>
            <div className="flex flex-col items-start gap-2 sm:items-end">
              <div className="text-sm text-gray-700">SSH: {sshHost}:{sshPort ?? '—'}</div>
              <div className="flex gap-2">
                <button className="btn btn-secondary" onClick={copySSH} disabled={!sshCmd}>Copy SSH</button>
                <button className="btn btn-secondary" onClick={stopVm} disabled={busy}>{busy ? <><Spinner className="h-4 w-4" /> Stop</> : 'Stop'}</button>
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
          <div className="mt-1 text-lg font-semibold">{(provider as any)?.resources?.cpu ?? '—'} vCPU</div>
        </div></div>
        <div className="card"><div className="card-body">
          <div className="text-sm text-gray-500">Memory</div>
          <div className="mt-1 text-lg font-semibold">{(provider as any)?.resources?.memory ?? '—'} GB</div>
        </div></div>
        <div className="card"><div className="card-body">
          <div className="text-sm text-gray-500">Storage</div>
          <div className="mt-1 text-lg font-semibold">{(provider as any)?.resources?.storage ?? '—'} GB</div>
        </div></div>
      </div>

      {/* Stream + Top-up */}
      <div className="card">
        <div className="card-body">
          {!vm.stream_id ? (
            <div className="text-sm text-gray-600">No stream mapped for this VM.</div>
          ) : !stream ? (
            <div className="text-sm text-gray-600">Loading stream…</div>
          ) : (
            <div className="grid gap-6 sm:grid-cols-2">
              <div className="grid gap-2 text-sm text-gray-700">
                <div className="flex items-center justify-between">
                  <div className="text-gray-500">Token</div>
                  <div className="font-mono">{tokenSymbol || (stream.chain.token?.toLowerCase()==='0x0000000000000000000000000000000000000000' ? 'ETH' : 'TOKEN')}</div>
                </div>
                <div className="flex items-center justify-between">
                  <div className="text-gray-500">Rate</div>
                  <div>
                    {(() => {
                      const dec = tokenDecimals || 18;
                      const rps = Number(stream.chain.ratePerSecond) / 10 ** dec;
                      const rph = rps * 3600;
                      if (displayCurrency === 'fiat' && usdPrice != null) {
                        const usdS = rps * usdPrice;
                        const usdH = rph * usdPrice;
                        return `$${usdS.toFixed(6)}/s ($${usdH.toFixed(6)}/h)`;
                      }
                      return `${rps.toFixed(6)} ${tokenSymbol || ''}/s (${rph.toFixed(6)} ${tokenSymbol || ''}/h)`;
                    })()}
                  </div>
                </div>
                <div className="flex items-center justify-between">
                  <div className="text-gray-500">Deposit</div>
                  <div>
                    {(() => {
                      const dec = tokenDecimals || 18;
                      const dep = Number(stream.chain.deposit) / 10 ** dec;
                      const wid = Number(stream.chain.withdrawn) / 10 ** dec;
                      const remTok = Math.max(0, dep - wid);
                      if (displayCurrency === 'fiat' && usdPrice != null) {
                        return `$${(remTok * usdPrice).toFixed(2)}`;
                      }
                      return `${remTok.toFixed(6)} ${tokenSymbol || ''}`;
                    })()}
                  </div>
                </div>
                <div className="flex items-center justify-between">
                  <div className="text-gray-500">Remaining</div>
                  <div className="font-medium">{humanDuration(remaining)}</div>
                </div>
                <div className="flex items-center justify-between">
                  <div className="text-gray-500">Status</div>
                  <div>{stream.chain.halted ? <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">● Halted</span> : <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">● Active</span>}</div>
                </div>
              </div>
              <div className="grid gap-3 content-start">
                <div className="text-sm text-gray-700">Top up stream</div>
                <div className="flex flex-wrap items-center gap-2">
                  <button className="btn btn-secondary" onClick={() => topUp(1800)} disabled={busy}>+30 min</button>
                  <button className="btn btn-secondary" onClick={() => topUp(3600)} disabled={busy}>{busy ? <><Spinner className="h-4 w-4" /> +1 h</> : '+1 h'}</button>
                  <button className="btn btn-secondary" onClick={() => topUp(7200)} disabled={busy}>+2 h</button>
                </div>
                <div className="flex items-center gap-2">
                  <input
                    className="input flex-1"
                    placeholder="Custom (e.g. 90, 45m, 2h 30m, 20s)"
                    value={customTopup}
                    onChange={(e) => setCustomTopup(e.target.value)}
                  />
                  <button
                    className="btn btn-secondary"
                    onClick={() => { const sec = parseTimeInput(customTopup); if (sec) topUp(sec); }}
                    disabled={busy || !customTopup.trim().length}
                  >Add</button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
