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
import { StreamCard } from "../../components/streams/StreamCard";

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
          const data = await fetchStreamWithMeta(spAddr, BigInt(r.stream_id!));
          list.push({ r, chain: data.chain as ChainStream, tokenSymbol: data.tokenSymbol, tokenDecimals: data.tokenDecimals, usdPrice: data.usdPrice });
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
      {!rentals.length && <div className="text-gray-600">No streams yet. Create a VM to open a stream.</div>}
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
