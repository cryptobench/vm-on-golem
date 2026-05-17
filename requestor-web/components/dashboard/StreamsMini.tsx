"use client";
import React from "react";
import { loadRentals, loadSettings, type Rental } from "../../lib/api";
import { useToast } from "@golem/ui";
import { getPaymentNetworkErrorMessage } from "../../lib/chain";
import { useWallet } from "../../context/WalletContext";
import { vmDetailsHref } from "../../lib/routes";
import {
  usePaymentStreamsLive,
  type PaymentStreamEntry,
} from "../../lib/paymentStreamLive";
import { getRequestorRuntimeConfig } from "../../lib/runtimeConfig";
import { isTerminatedStream } from "../../lib/streams";
import { StreamCard } from "../streams/StreamCard";
import { useStreamActions } from "../../hooks/useStreamActions";

export function StreamsMini({ projectId }: { projectId: string }) {
  const rentals = (loadRentals() || []).filter(r => r.stream_id && (r.project_id || 'default') === projectId);
  const { show } = useToast();
  const [busy, setBusy] = React.useState<string | null>(null);
  const spAddr = (loadSettings().stream_payment_address || getRequestorRuntimeConfig().streamPaymentAddress || '').trim();
  const [displayCurrency, setDisplayCurrency] = React.useState<'fiat'|'token'>(loadSettings().display_currency === 'token' ? 'token' : 'fiat');
  const { paymentReady, paymentMessage } = useWallet();
  const liveStreams = usePaymentStreamsLive(spAddr, rentals);
  const liveEntries = rentals.map((r) => liveStreams.entries[String(r.stream_id)]);
  const rows = liveEntries.some((entry) => !entry)
    ? null
    : liveEntries.filter(
        (entry): entry is Extract<PaymentStreamEntry, { ok: true }> =>
          entry?.ok &&
          !isTerminatedStream(entry.data.chain) &&
          entry.data.remaining > 0n,
      );
  const firstEntryError = liveEntries.find((entry) => entry && !entry.ok);
  const error =
    liveStreams.error ||
    (firstEntryError && !firstEntryError.ok ? firstEntryError.error : null);
  // Listen for settings changes (fiat/token toggle)
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

  const { topUp } = useStreamActions(spAddr);
  const topUpSeconds = async (r: Rental, rate: bigint, token: string, seconds: number) => {
    try {
      setBusy(r.vm_id);
      await topUp(BigInt(r.stream_id!), token, rate, seconds);
      show("Top-up sent");
      await liveStreams.refresh();
    } catch (e) {
      show(getPaymentNetworkErrorMessage(e));
    } finally { setBusy(null); }
  };

  return (
    <div className="space-y-4">
      <h2>Streams</h2>
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
              <StreamCard
                title={row.rental.name}
                streamId={row.rental.stream_id}
                chain={row.data.chain}
                remaining={Number(row.data.remaining)}
                meta={{ tokenSymbol: row.data.tokenSymbol, tokenDecimals: row.data.tokenDecimals, usdPrice: row.data.usdPrice }}
                displayCurrency={displayCurrency}
                detailsHref={vmDetailsHref(row.rental.vm_id)}
                onTopUp={(secs) => topUpSeconds(row.rental, row.data.chain.ratePerSecond, row.data.chain.token, secs)}
                busy={busy === row.rental.vm_id}
                actionsDisabled={!paymentReady}
                actionsDisabledReason={!paymentReady ? paymentMessage : null}
              />
            </div>
          ))
        )}
      </div>
    </div>
  );
}
