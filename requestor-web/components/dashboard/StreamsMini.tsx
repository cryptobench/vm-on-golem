"use client";
import React from "react";
import { BrowserProvider, Contract } from "ethers";
import { loadRentals, loadSettings, type Rental } from "../../lib/api";
import { useToast } from "../ui/Toast";
import { Spinner } from "../ui/Spinner";
import { ensureNetwork, getPaymentsChain } from "../../lib/chain";
import { useWallet } from "../../context/WalletContext";
import { fetchStreamWithMeta } from "../../lib/streams";
import { StreamCard } from "../streams/StreamCard";
import streamPayment from "../../public/abi/StreamPayment.json";

export function StreamsMini({ projectId }: { projectId: string }) {
  const rentals = (loadRentals() || []).filter(r => r.stream_id && (r.project_id || 'default') === projectId);
  const { show } = useToast();
  const [rows, setRows] = React.useState<any[] | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState<string | null>(null);
  const spAddr = (loadSettings().stream_payment_address || process.env.NEXT_PUBLIC_STREAM_PAYMENT_ADDRESS || '').trim();
  const { account } = useWallet();

  const load = async () => {
    if (!spAddr || !rentals.length) { setRows([]); return; }
    setError(null);
    try {
      setRows(null);
      const list = await Promise.all(rentals.map(async r => {
        try {
          const data = await fetchStreamWithMeta(spAddr, BigInt(r.stream_id!));
          return { ok: true, r, data };
        } catch (e: any) {
          return { ok: false, r, error: e?.message || String(e) };
        }
      }));
      // Dashboard: show only active (not halted and remaining > 0)
      const filtered = list.filter(row => row.ok && row.data && !row.data.chain.halted && (row.data.remaining > 0));
      setRows(filtered);
    } catch (e: any) { setError(e?.message || String(e)); }
  };

  React.useEffect(() => { load(); }, [projectId]);

  const topUpOneHour = async (r: Rental, rate: bigint, token: string) => {
    try {
      const addWei = rate * 3600n;
      setBusy(r.vm_id);
      const { ethereum } = window as any;
      await ensureNetwork(ethereum, getPaymentsChain());
      const provider = new BrowserProvider(ethereum);
      const signer = await provider.getSigner(account ?? undefined);
      const contract = new Contract(spAddr, (streamPayment as any).abi, signer);
      const streamId = BigInt(r.stream_id!);
      const tx = await contract.topUp(streamId, addWei, {
        value: token === '0x0000000000000000000000000000000000000000' ? addWei : 0n,
        gasLimit: 150000n,
      });
      await tx.wait();
      show("Top-up sent");
      await load();
    } catch (e) {
      show("Top-up failed");
    } finally { setBusy(null); }
  };

  return (
    <div className="space-y-4">
      <h2>Payment Streams</h2>
      {!rentals.length && <div className="text-gray-600 text-sm">No streams in this project.</div>}
      {error && <div className="text-sm text-red-600">{error}</div>}
      <div className="grid gap-6 sm:grid-cols-2">
        {rows === null ? (
          Array.from({ length: Math.min(4, Math.max(1, rentals.length)) }).map((_, i) => (
            <div key={i} className="card"><div className="card-body"><div className="h-4 w-48 bg-gray-100 rounded" /></div></div>
          ))
        ) : (
          rows.map((row, i) => (
            <div key={i}>
              {!row.ok ? (
                <div className="card"><div className="card-body"><div className="text-sm text-red-600">{row.error}</div></div></div>
              ) : (
                <StreamCard
                  title={row.r.name}
                  streamId={row.r.stream_id}
                  chain={row.data.chain}
                  remaining={row.data.remaining}
                  meta={{ tokenSymbol: row.data.tokenSymbol, tokenDecimals: row.data.tokenDecimals, usdPrice: row.data.usdPrice }}
                  displayCurrency={(loadSettings().display_currency === 'token' ? 'token' : 'fiat')}
                  detailsHref={`/vm?id=${encodeURIComponent(row.r.vm_id)}`}
                  onTopUp={(secs) => topUpOneHour(row.r, row.data.chain.ratePerSecond, row.data.chain.token)}
                  busy={busy === row.r.vm_id}
                />
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
