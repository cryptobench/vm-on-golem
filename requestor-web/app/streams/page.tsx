"use client";
import React from "react";
import { useRouter } from "next/navigation";
import { BrowserProvider, Contract } from "ethers";
import streamPayment from "../../public/abi/StreamPayment.json";
import { loadRentals, loadSettings } from "../../lib/api";
import { Spinner } from "../../components/ui/Spinner";
import { Skeleton } from "../../components/ui/Skeleton";
import { useToast } from "../../components/ui/Toast";
import { ensureNetwork, getPaymentsChain } from "../../lib/chain";
import { useWallet } from "../../context/WalletContext";
import { fetchStreamWithMeta } from "../../lib/streams";
import { getPriceUSD, onPricesUpdated } from "../../lib/prices";
import { StreamCard } from "../../components/streams/StreamCard";
import { RiCheckboxCircleFill, RiTimeFill, RiStackLine } from "@remixicon/react";

type ChainStream = {
  token: string; sender: string; recipient: string;
  startTime: bigint; stopTime: bigint; ratePerSecond: bigint;
  deposit: bigint; withdrawn: bigint; halted: boolean;
};

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
  const [rentals, setRentals] = React.useState<ReturnType<typeof loadRentals> | null>(null);
  const [rows, setRows] = React.useState<Row[] | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const spAddr = (loadSettings().stream_payment_address || process.env.NEXT_PUBLIC_STREAM_PAYMENT_ADDRESS || '').trim();
  const glmAddr = (loadSettings().glm_token_address || process.env.NEXT_PUBLIC_GLM_TOKEN_ADDRESS || '').toLowerCase();
  const [displayCurrency, setDisplayCurrency] = React.useState<'fiat'|'token'>(loadSettings().display_currency === 'token' ? 'token' : 'fiat');
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
      for (const r of (rentals || []).filter(r => r.stream_id)) {
        try {
          const data = await fetchStreamWithMeta(spAddr, BigInt(r.stream_id!));
          list.push({ r, chain: data.chain as ChainStream, tokenSymbol: data.tokenSymbol, tokenDecimals: data.tokenDecimals, usdPrice: data.usdPrice });
        } catch {}
      }
      setRows(list);
    } catch (e: any) { setError(e?.message || String(e)); }
  };

  // Mount-gate rentals to avoid SSR hydration mismatch from localStorage
  React.useEffect(() => {
    const t = setTimeout(() => setRentals(loadRentals()), 0);
    return () => clearTimeout(t);
  }, []);

  // Load stream rows once rentals are available
  React.useEffect(() => { if (rentals) load(); }, [rentals]);
  // React to settings changes (e.g., fiat/token toggle) without reload
  React.useEffect(() => {
    const onSettings = (e: any) => {
      try {
        const mode = (e?.detail?.display_currency === 'token' ? 'token' : 'fiat') as 'fiat'|'token';
        setDisplayCurrency(mode);
      } catch {}
    };
    const onStorage = () => {
      const cur = (loadSettings().display_currency === 'token' ? 'token' : 'fiat') as 'fiat'|'token';
      setDisplayCurrency(cur);
    };
    window.addEventListener('requestor_settings_changed', onSettings as any);
    window.addEventListener('storage', onStorage);
    return () => {
      window.removeEventListener('requestor_settings_changed', onSettings as any);
      window.removeEventListener('storage', onStorage);
    };
  }, []);

  // React to global price updates and refresh USD mappings in place
  React.useEffect(() => {
    const off = onPricesUpdated(() => {
      setRows(prev => {
        if (!prev) return prev;
        return prev.map(row => {
          const sym = (row.tokenSymbol || '').toUpperCase();
          const p = (sym === 'ETH' || sym === 'WETH') ? getPriceUSD('ETH') : (sym === 'GLM' ? getPriceUSD('GLM') : null);
          return { ...row, usdPrice: p };
        });
      });
    });
    return () => { try { off && off(); } catch {} };
  }, []);

  const refreshOne = async (streamId: string) => {
    try {
      const idx = rows?.findIndex(x => String(x.r.stream_id) === String(streamId));
      if (idx == null || idx < 0 || !rows) return;
      const data = await fetchStreamWithMeta(spAddr, BigInt(streamId));
      const cur = rows[idx];
      const next = [...rows];
      next[idx] = {
        ...cur,
        chain: data.chain as ChainStream,
        tokenSymbol: data.tokenSymbol,
        tokenDecimals: data.tokenDecimals,
        usdPrice: data.usdPrice,
      };
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

  // Partition streams into active vs ended (depleted or halted)
  const renderRows = (list: Row[], allowTopUp: boolean) => (
    <div className="grid gap-6 sm:grid-cols-2">
      {list.map((row, i) => {
        const sid = String(row.r.stream_id);
        const isBusy = !!busy[sid];
        const remaining = Math.max(0, Number(row.chain.stopTime || 0n) - nowSec);
        return (
          <StreamCard
            key={i}
            title={row.r.name}
            streamId={row.r.stream_id}
            chain={row.chain as any}
            remaining={remaining}
            meta={{ tokenSymbol: row.tokenSymbol, tokenDecimals: row.tokenDecimals, usdPrice: row.usdPrice }}
            displayCurrency={displayCurrency}
            onTopUp={allowTopUp && !row.chain.halted ? ((secs) => topUp(row, secs)) : undefined}
            busy={isBusy}
            detailsHref={`/vm?id=${encodeURIComponent(row.r.vm_id)}`}
          />
        );
      })}
    </div>
  );

  let active: Row[] = [];
  let ended: Row[] = [];
  if (rows && rows.length) {
    active = rows.filter(row => !row.chain.halted && (Number(row.chain.stopTime || 0n) - nowSec) > 0);
    ended = rows.filter(row => row.chain.halted || (Number(row.chain.stopTime || 0n) - nowSec) <= 0);
  }

  return (
    <div className="space-y-6">
      <h2>Streams</h2>
      {/* Aggregates */}
      {rows === null ? (
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="card"><div className="card-body"><Skeleton className="h-6 w-24" /><div className="mt-2"><Skeleton className="h-4 w-20" /></div></div></div>
          <div className="card"><div className="card-body"><Skeleton className="h-6 w-28" /><div className="mt-2"><Skeleton className="h-4 w-28" /></div></div></div>
          <div className="card"><div className="card-body"><Skeleton className="h-6 w-32" /><div className="mt-2"><Skeleton className="h-4 w-24" /></div></div></div>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-3">
          {/* Active / Ended count */}
          <div className="card"><div className="card-body">
            <div className="text-sm text-gray-600 inline-flex items-center gap-1.5"><RiCheckboxCircleFill className="h-4 w-4 text-gray-500" /> Active streams</div>
            <div className="mt-1 text-2xl font-semibold text-gray-900">{active.length}</div>
            {ended.length > 0 && (
              <div className="mt-1 text-xs text-gray-600">Ended: {ended.length}</div>
            )}
          </div></div>
          {/* Hourly burn */}
          <div className="card"><div className="card-body">
            <div className="text-sm text-gray-600 inline-flex items-center gap-1.5"><RiTimeFill className="h-4 w-4 text-gray-500" /> Hourly burn</div>
            {(() => {
              // Compute sums for active only
              const unknown: string[] = [];
              if (displayCurrency === 'fiat') {
                let totalUsd = 0;
                for (const row of active) {
                  const dec = row.tokenDecimals || 18;
                  const rpsTok = Number(row.chain.ratePerSecond) / 10 ** dec;
                  if (row.usdPrice != null) totalUsd += rpsTok * 3600 * row.usdPrice;
                  else unknown.push(String(row.r.stream_id));
                }
                return (
                  <>
                    <div className="mt-1 text-2xl font-semibold text-gray-900">${totalUsd.toFixed(6)}/h</div>
                    {unknown.length > 0 && (
                      <div className="mt-1 text-xs text-gray-600">+ ? from {unknown.length} stream{unknown.length===1?'':'s'}</div>
                    )}
                  </>
                );
              } else {
                const perToken: Record<string, number> = {};
                for (const row of active) {
                  const dec = row.tokenDecimals || 18;
                  const rpsTok = Number(row.chain.ratePerSecond) / 10 ** dec;
                  const sym = row.tokenSymbol || 'TOKEN';
                  perToken[sym] = (perToken[sym] || 0) + (rpsTok * 3600);
                }
                const entries = Object.entries(perToken);
                return (
                  <div className="mt-1 flex flex-wrap gap-2">
                    {entries.length === 0 ? (
                      <div className="text-2xl font-semibold text-gray-900">0</div>
                    ) : entries.map(([sym, v]) => (
                      <span key={sym} className="inline-flex items-center gap-1.5 rounded bg-gray-50 px-2.5 py-1 text-xs font-medium text-gray-700">
                        <span className="text-gray-900 font-semibold">{v.toFixed(6)}</span>
                        <span>{sym}/h</span>
                      </span>
                    ))}
                  </div>
                );
              }
            })()}
          </div></div>
          {/* Remaining balance */}
          <div className="card"><div className="card-body">
            <div className="text-sm text-gray-600 inline-flex items-center gap-1.5"><RiStackLine className="h-4 w-4 text-gray-500" /> Remaining balance</div>
            {(() => {
              const unknown: string[] = [];
              if (displayCurrency === 'fiat') {
                let totalUsd = 0;
                for (const row of active) {
                  const dec = row.tokenDecimals || 18;
                  const rpsTok = Number(row.chain.ratePerSecond) / 10 ** dec;
                  const remSec = Math.max(0, Number(row.chain.stopTime || 0n) - nowSec);
                  const reqRemainingTok = Math.max(0, rpsTok * remSec);
                  if (row.usdPrice != null) totalUsd += reqRemainingTok * row.usdPrice;
                  else unknown.push(String(row.r.stream_id));
                }
                return (
                  <>
                    <div className="mt-1 text-2xl font-semibold text-gray-900">${totalUsd.toFixed(2)}</div>
                    {unknown.length > 0 && (
                      <div className="mt-1 text-xs text-gray-600">+ ? from {unknown.length} stream{unknown.length===1?'':'s'}</div>
                    )}
                  </>
                );
              } else {
                const perToken: Record<string, number> = {};
                for (const row of active) {
                  const dec = row.tokenDecimals || 18;
                  const rpsTok = Number(row.chain.ratePerSecond) / 10 ** dec;
                  const remSec = Math.max(0, Number(row.chain.stopTime || 0n) - nowSec);
                  const reqRemainingTok = Math.max(0, rpsTok * remSec);
                  const sym = row.tokenSymbol || 'TOKEN';
                  perToken[sym] = (perToken[sym] || 0) + reqRemainingTok;
                }
                const entries = Object.entries(perToken);
                return (
                  <div className="mt-1 flex flex-wrap gap-2">
                    {entries.length === 0 ? (
                      <div className="text-2xl font-semibold text-gray-900">0</div>
                    ) : entries.map(([sym, v]) => (
                      <span key={sym} className="inline-flex items-center gap-1.5 rounded bg-gray-50 px-2.5 py-1 text-xs font-medium text-gray-700">
                        <span className="text-gray-900 font-semibold">{v.toFixed(6)}</span>
                        <span>{sym}</span>
                      </span>
                    ))}
                  </div>
                );
              }
            })()}
          </div></div>
        </div>
      )}
      {rentals !== null && rentals.filter(r => r.stream_id).length === 0 && (
        <div className="text-gray-600">No streams yet. Create a VM to open a stream.</div>
      )}
      {error && <div className="text-sm text-red-600">{error}</div>}
      {rows === null ? (
        <div className="grid gap-6 sm:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="card">
              <div className="card-body">
                <Skeleton className="h-4 w-48" />
                <div className="mt-4 grid grid-cols-2 gap-3">
                  <Skeleton className="h-3 w-full" />
                  <Skeleton className="h-3 w-full" />
                  <Skeleton className="h-3 w-3/4" />
                  <Skeleton className="h-3 w-2/3" />
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <>
          {active.length ? (
            <div>
              <div className="mb-2 text-sm text-gray-700">Active</div>
              {renderRows(active, true)}
            </div>
          ) : (
            <div className="text-gray-600">No active streams.</div>
          )}
          {ended.length > 0 && (
            <div>
              <div className="mt-4 mb-2 text-sm text-gray-700">Ended</div>
              {renderRows(ended, false)}
            </div>
          )}
        </>
      )}
    </div>
  );
}
