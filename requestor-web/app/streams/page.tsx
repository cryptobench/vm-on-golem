"use client";
import React from "react";
import { BrowserProvider, Contract } from "ethers";
import streamPayment from "../../public/abi/StreamPayment.json";
import { loadRentals, loadSettings } from "../../lib/api";
import { Spinner } from "../../components/ui/Spinner";
import { Skeleton } from "../../components/ui/Skeleton";

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

export default function StreamsPage() {
  const rentals = loadRentals().filter(r => r.stream_id);
  const [rows, setRows] = React.useState<any[] | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const spAddr = (loadSettings().stream_payment_address || process.env.NEXT_PUBLIC_STREAM_PAYMENT_ADDRESS || '').trim();

  const load = async () => {
    if (!spAddr) { setError("StreamPayment address not configured (Settings)"); return; }
    setError(null);
    try {
      setRows(null);
      const list = await Promise.all(rentals.map(async r => {
        try {
          const data = await fetchStream(spAddr, BigInt(r.stream_id!));
          return { ok: true, r, data };
        } catch (e: any) {
          return { ok: false, r, error: e?.message || String(e) };
        }
      }));
      setRows(list);
    } catch (e: any) { setError(e?.message || String(e)); }
  };

  React.useEffect(() => { load(); }, []);

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
          rows.map((row, i) => (
            <div key={i} className="card">
              <div className="card-body">
                <div className="font-semibold">{row.r.name} — Stream {row.r.stream_id}</div>
                {!row.ok ? (
                  <div className="mt-2 text-sm text-red-600">{row.error}</div>
                ) : (
                  <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <div className="text-sm text-gray-700">
                      <div><span className="text-gray-500">Recipient:</span> {row.data.chain.recipient}</div>
                      <div><span className="text-gray-500">Token:</span> {row.data.chain.token}</div>
                      <div><span className="text-gray-500">Rate/s (wei):</span> {row.data.chain.ratePerSecond.toString()}</div>
                    </div>
                    <div className="text-sm text-gray-700">
                      <div><span className="text-gray-500">Deposit:</span> {row.data.chain.deposit.toString()}</div>
                      <div><span className="text-gray-500">Withdrawn:</span> {row.data.chain.withdrawn.toString()}</div>
                      <div><span className="text-gray-500">Status:</span> {row.data.chain.halted ? 'halted' : 'active'}</div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
