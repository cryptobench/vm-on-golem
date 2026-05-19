"use client";

import React from "react";
import { Contract, WebSocketProvider } from "ethers";
import streamPayment from "../public/abi/StreamPayment.json";
import { loadSettings, type Rental } from "./api";
import { getPaymentsChain, getPaymentsWsUrl, normalizeChainId } from "./chain";
import {
  fetchStreamWithMetaFromProvider,
  type ChainStream,
} from "./streams";

export type PaymentStreamData = {
  chain: ChainStream;
  remaining: bigint;
  tokenSymbol: string;
  tokenDecimals: number;
  usdPrice: number | null;
};

export type PaymentStreamEntry =
  | { ok: true; rental: Rental; data: PaymentStreamData }
  | { ok: false; rental: Rental; error: string };

const STREAM_EVENT_NAMES = [
  "StreamCreated",
  "Withdraw",
  "Terminated",
  "ToppedUp",
] as const;

export function usePaymentStreamsLive(
  streamPaymentAddress: string,
  rentals: Rental[],
) {
  const [entries, setEntries] = React.useState<Record<string, PaymentStreamEntry>>(
    {},
  );
  const [error, setError] = React.useState<string | null>(null);
  const [connected, setConnected] = React.useState(false);
  const [refreshNonce, setRefreshNonce] = React.useState(0);
  const streamRentals = React.useMemo(
    () => rentals.filter((rental) => rental.stream_id),
    [rentals],
  );
  const streamKey = streamRentals
    .map((rental) => `${rental.vm_id}:${rental.stream_id || ""}`)
    .join("|");

  React.useEffect(() => {
    if (!streamPaymentAddress || streamRentals.length === 0) {
      setEntries({});
      setError(null);
      setConnected(false);
      return;
    }

    let cancelled = false;
    const settings = loadSettings();
    const wsUrl = getPaymentsWsUrl(settings);
    const expectedChain = getPaymentsChain(settings);
    const streamIds = new Set(
      streamRentals.map((rental) => String(rental.stream_id)),
    );
    const provider = new WebSocketProvider(wsUrl);
    const contract = new Contract(
      streamPaymentAddress,
      (streamPayment as any).abi,
      provider,
    );

    async function loadOne(rental: Rental) {
      try {
        const data = await fetchStreamWithMetaFromProvider(
          streamPaymentAddress,
          BigInt(rental.stream_id!),
          provider,
        );
        if (cancelled) return;
        setEntries((current) => ({
          ...current,
          [String(rental.stream_id)]: { ok: true, rental, data },
        }));
      } catch (caught) {
        if (cancelled) return;
        setEntries((current) => ({
          ...current,
          [String(rental.stream_id)]: {
            ok: false,
            rental,
            error: caught instanceof Error ? caught.message : String(caught),
          },
        }));
      }
    }

    async function run() {
      try {
        const network = await provider.getNetwork();
        if (
          normalizeChainId(Number(network.chainId)) !==
          normalizeChainId(expectedChain.chainId)
        ) {
          throw new Error(
            `Payments WS chain mismatch: expected ${expectedChain.chainId}, got ${network.chainId}`,
          );
        }
        if (cancelled) return;
        setConnected(true);
        setError(null);
        await Promise.all(streamRentals.map((rental) => loadOne(rental)));
        for (const eventName of STREAM_EVENT_NAMES) {
          contract.on(eventName, async (...args: any[]) => {
            try {
              const event = args.at(-1);
              const parsed =
                event?.args ||
                (event?.log ? contract.interface.parseLog(event.log)?.args : null);
              const streamId =
                parsed?.streamId == null ? null : String(parsed.streamId);
              if (!streamId || !streamIds.has(streamId)) return;
              const rental = streamRentals.find(
                (item) => String(item.stream_id) === streamId,
              );
              if (rental) await loadOne(rental);
            } catch (caught) {
              if (!cancelled) {
                setError(caught instanceof Error ? caught.message : String(caught));
              }
            }
          });
        }
      } catch (caught) {
        if (!cancelled) {
          setConnected(false);
          setError(caught instanceof Error ? caught.message : String(caught));
        }
      }
    }

    void run();
    return () => {
      cancelled = true;
      contract.removeAllListeners();
      void provider.destroy();
    };
  }, [streamPaymentAddress, streamKey, refreshNonce]);

  const refresh = React.useCallback(async () => {
    setRefreshNonce((current) => current + 1);
  }, []);

  return {
    connected,
    entries,
    error,
    refresh,
  };
}
