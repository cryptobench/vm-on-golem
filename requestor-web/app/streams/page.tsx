"use client";
import React from "react";
import { useRouter } from "next/navigation";
import { BrowserProvider, Contract } from "ethers";
import streamPayment from "../../public/abi/StreamPayment.json";
import erc20 from "../../public/abi/ERC20.json";
import { loadRentals, loadSettings } from "../../lib/api";
import { Spinner } from "../../components/ui/Spinner";
import { Skeleton } from "../../components/ui/Skeleton";
import { useToast } from "../../components/ui/Toast";
import { ensureNetwork, getPaymentsChain } from "../../lib/chain";
import { useWallet } from "../../context/WalletContext";

type ChainStream = {
  token: string; sender: string; recipient: string;
  startTime: bigint; stopTime: bigint; ratePerSecond: bigint;
  deposit: bigint; withdrawn: bigint; halted: boolean;
};

async function fetchStream(spAddr: string, id: bigint) {
  const { ethereum } = window as any;
  const provider = new BrowserProvider(ethereum);
  const contract = new Contract(spAddr, (streamPayment as any).abi, provider);
  const res = (await contract.streams(id)) as ChainStream;
  return { chain: res };
}

type Row = {
  r: ReturnType<typeof loadRentals>[number];
  chain: ChainStream;
  tokenSymbol: string;
  tokenDecimals: number;
  usdPrice: number | null;
};

export default function StreamsPage() {
  const router = useRouter();
  const { show } = useToast();
  const { account } = useWallet();
  const rentals = loadRentals().filter(r => r.stream_id);
  const [rows, setRows] = React.useState<Row[] | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const spAddr = (loadSettings().stream_payment_address || process.env.NEXT_PUBLIC_STREAM_PAYMENT_ADDRESS || '').trim();
  const glmAddr = (loadSettings().glm_token_address || process.env.NEXT_PUBLIC_GLM_TOKEN_ADDRESS || '').toLowerCase();
  const displayCurrency = (loadSettings().display_currency === 'token' ? 'token' : 'fiat');
  const [nowSec, setNowSec] = React.useState<number>(() => Math.floor(Date.now()/1000));
  const [busy, setBusy] = React.useState<Record<string, boolean>>({});
  const [customTopup, setCustomTopup] = React.useState<Record<string, string>>({});
  React.useEffect(() => { const t = setInterval(() => setNowSec(Math.floor(Date.now()/1000)), 1000); return () => clearInterval(t); }, []);

  const load = async () => {
    if (!spAddr) { setError("StreamPayment address not configured (Settings)"); return; }
    setError(null);
    try {
      setRows(null);
      const list: Row[] = [];
      for (const r of rentals) {
        try {
          const data = await fetchStream(spAddr, BigInt(r.stream_id!));
          // Token meta + USD price (best-effort)
          let tokenSymbol = 'ETH';
          let tokenDecimals = 18;
          let usdPrice: number | null = null;
          try {
            const { ethereum } = window as any;
            const provider = new BrowserProvider(ethereum);
            const zero = '0x0000000000000000000000000000000000000000';
            if (data.chain.token && data.chain.token.toLowerCase() !== zero) {
              const erc = new Contract(data.chain.token, (erc20 as any).abi, provider);
              tokenSymbol = String(await erc.symbol().catch(() => 'TOKEN'));
              tokenDecimals = Number(await erc.decimals().catch(() => 18));
            } else { tokenSymbol = 'ETH'; tokenDecimals = 18; }
            if (data.chain.token.toLowerCase() === zero) {
              const r = await fetch('https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd');
              const js = await r.json().catch(() => ({}));
              usdPrice = js?.ethereum?.usd ?? null;
            } else if (glmAddr && data.chain.token.toLowerCase() === glmAddr) {
              const r = await fetch('https://api.coingecko.com/api/v3/simple/price?ids=golem&vs_currencies=usd');
              const js = await r.json().catch(() => ({}));
              usdPrice = js?.golem?.usd ?? null;
            }
          } catch { usdPrice = null; }
          list.push({ r, chain: data.chain, tokenSymbol, tokenDecimals, usdPrice });
        } catch {}
      }
      setRows(list);
    } catch (e: any) { setError(e?.message || String(e)); }
  };

  React.useEffect(() => { load(); }, []);

  const refreshOne = async (streamId: string) => {
    try {
      const idx = rows?.findIndex(x => String(x.r.stream_id) === String(streamId));
      if (idx == null || idx < 0 || !rows) return;
      const updated = await fetchStream(spAddr, BigInt(streamId));
      const cur = rows[idx];
      const next = [...rows];
      next[idx] = { ...cur, chain: updated.chain };
      setRows(next);
    } catch {}
  };

  const topUp = async (row: Row, seconds: number) => {
    const sid = String(row.r.stream_id);
    try {
      if (!sid || !spAddr) return;
      setBusy(prev => ({ ...prev, [sid]: true }));
      const { ethereum } = window as any;
      await ensureNetwork(ethereum, getPaymentsChain());
      const provider = new BrowserProvider(ethereum);
      const signer = await provider.getSigner(account ?? undefined);
      const contract = new Contract(spAddr, (streamPayment as any).abi, signer);
      const addWei = row.chain.ratePerSecond * BigInt(seconds);
      const zero = '0x0000000000000000000000000000000000000000';
      const tx = await contract.topUp(BigInt(sid), addWei, {
        value: row.chain.token?.toLowerCase() === zero ? addWei : 0n,
        gasLimit: 150000n,
      });
      await tx.wait();
      show("Top-up sent");
      await refreshOne(sid);
    } catch (e) {
      show("Top-up failed");
    } finally {
      setBusy(prev => ({ ...prev, [sid]: false }));
    }
  };

  return (
    <div className="space-y-4">
      <h2>Streams</h2>
      {!rentals.length && <div className="text-gray-600">No streams yet. Create a VM to open a stream.</div>}
      {error && <div className="text-sm text-red-600">{error}</div>}
      <div className="grid gap-4 sm:grid-cols-2">
        {rows === null ? (
          Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="card">
              <div className="card-body">
                <Skeleton className="h-4 w-48" />
                <div className="mt-3 grid grid-cols-2 gap-3">
                  <Skeleton className="h-3 w-full" />
                  <Skeleton className="h-3 w-full" />
                  <Skeleton className="h-3 w-3/4" />
                  <Skeleton className="h-3 w-2/3" />
                </div>
              </div>
            </div>
          ))
        ) : (
          rows.map((row, i) => {
            const dec = row.tokenDecimals || 18;
            const rps = Number(row.chain.ratePerSecond) / 10 ** dec;
            const rph = rps * 3600;
            const dep = Number(row.chain.deposit) / 10 ** dec;
            const wid = Number(row.chain.withdrawn) / 10 ** dec;
            const remTok = Math.max(0, dep - wid);
            const stop = Number(row.chain.stopTime || 0n);
            const remaining = Math.max(0, stop - nowSec);
            const human = (s: number) => {
              const x = Math.max(0, Math.floor(s));
              const d = Math.floor(x / 86400);
              const h = Math.floor((x % 86400) / 3600);
              const m = Math.floor((x % 3600) / 60);
              const sec = x % 60;
              const parts: string[] = [];
              if (d) parts.push(`${d} day${d!==1?'s':''}`);
              if (h) parts.push(`${h} hour${h!==1?'s':''}`);
              if (m) parts.push(`${m} minute${m!==1?'s':''}`);
              if (sec && parts.length < 2) parts.push(`${sec} second${sec!==1?'s':''}`);
              return parts.length ? parts.join(', ') : '0 seconds';
            };
            const sid = String(row.r.stream_id);
            const isBusy = !!busy[sid];
            return (
              <div key={i} className="card cursor-pointer" onClick={() => router.push(`/vm?id=${encodeURIComponent(row.r.vm_id)}`)}>
                <div className="card-body">
                  <div className="flex items-center justify-between gap-2">
                    <div className="font-semibold truncate">{row.r.name} — Stream {row.r.stream_id}</div>
                  </div>
                  <div className="mt-3 grid gap-2 text-sm text-gray-700 sm:grid-cols-2">
                    <div className="flex items-center justify-between"><div className="text-gray-500">Token</div><div className="font-mono">{row.tokenSymbol}</div></div>
                    <div className="flex items-center justify-between"><div className="text-gray-500">Rate</div><div>
                      {displayCurrency === 'fiat' && row.usdPrice != null ? (
                        <>${(rps * row.usdPrice).toFixed(6)}/s (${(rph * row.usdPrice).toFixed(6)}/h)</>
                      ) : (
                        <>{rps.toFixed(6)} {row.tokenSymbol}/s ({rph.toFixed(6)} {row.tokenSymbol}/h)</>
                      )}
                    </div></div>
                    <div className="flex items-center justify-between"><div className="text-gray-500">Deposit</div><div>
                      {displayCurrency === 'fiat' && row.usdPrice != null ? (
                        <>${(remTok * row.usdPrice).toFixed(2)}</>
                      ) : (
                        <>{remTok.toFixed(6)} {row.tokenSymbol}</>
                      )}
                    </div></div>
                    <div className="flex items-center justify-between"><div className="text-gray-500">Remaining</div><div className="font-medium">{human(remaining)}</div></div>
                    <div className="flex items-center justify-between"><div className="text-gray-500">Status</div><div>{row.chain.halted ? <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">● Halted</span> : <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">● Active</span>}</div></div>
                  </div>
                  {/* Top-up actions */}
                  <div className="mt-4 grid gap-3 content-start" onClick={(e) => e.stopPropagation()}>
                    <div className="text-sm text-gray-700">Top up stream</div>
                    <div className="flex flex-wrap items-center gap-2">
                      <button className="btn btn-secondary" onClick={(e) => { e.stopPropagation(); topUp(row, 1800); }} disabled={isBusy}>+30 min</button>
                      <button className="btn btn-secondary" onClick={(e) => { e.stopPropagation(); topUp(row, 3600); }} disabled={isBusy}>{isBusy ? (<><Spinner className="h-4 w-4" /> +1 h</>) : '+1 h'}</button>
                      <button className="btn btn-secondary" onClick={(e) => { e.stopPropagation(); topUp(row, 7200); }} disabled={isBusy}>+2 h</button>
                    </div>
                    <div className="flex items-center gap-2">
                      <input
                        className="input flex-1"
                        placeholder="Custom (e.g. 90, 45m, 2h 30m, 20s)"
                        value={customTopup[sid] || ''}
                        onChange={(e) => setCustomTopup(prev => ({ ...prev, [sid]: e.target.value }))}
                      />
                      <button
                        className="btn btn-secondary"
                        onClick={(e) => {
                          e.stopPropagation();
                          const t = (customTopup[sid] || '').trim().toLowerCase();
                          let seconds = 0;
                          if (/^\d+$/.test(t)) seconds = parseInt(t, 10) * 60;
                          else {
                            const re = /(\d+)\s*(h|m|s)/g; let m; while ((m = re.exec(t))) {
                              const n = parseInt(m[1], 10); const u = m[2];
                              if (u === 'h') seconds += n * 3600; else if (u === 'm') seconds += n * 60; else seconds += n;
                            }
                          }
                          if (seconds > 0) topUp(row, seconds);
                        }}
                        disabled={isBusy || !(customTopup[sid] || '').trim().length}
                      >Add</button>
                    </div>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
