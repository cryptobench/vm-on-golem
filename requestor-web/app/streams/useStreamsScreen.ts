"use client";

import React from "react";
import { useWallet } from "../../context/WalletContext";
import { useStreamActions } from "../../hooks/useStreamActions";
import {
  loadRentals,
  loadSettings,
  saveSettings,
  type Rental,
} from "../../lib/api";
import { getPaymentNetworkErrorMessage } from "../../lib/chain";
import { usePaymentStreamsLive } from "../../lib/paymentStreamLive";
import { getPriceUSD, onPricesUpdated } from "../../lib/prices";
import { getRequestorRuntimeConfig } from "../../lib/runtimeConfig";
import { useToast } from "@golem/ui";
import {
  isEndedStream,
  type DisplayCurrency,
  type StreamRow,
} from "../../components/streams/streamModel";

export function useStreamsScreen() {
  const { show } = useToast();
  const { paymentReady, paymentMessage } = useWallet();
  const [mounted, setMounted] = React.useState(false);
  const [rentals, setRentals] = React.useState<Rental[]>([]);
  const [rows, setRows] = React.useState<StreamRow[] | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState<Record<string, boolean>>({});
  const [refreshing, setRefreshing] = React.useState(false);
  const [showEnded, setShowEnded] = React.useState(false);
  const [nowSec, setNowSec] = React.useState(() =>
    Math.floor(Date.now() / 1000),
  );
  const [displayCurrency, setDisplayCurrency] =
    React.useState<DisplayCurrency>("fiat");
  const [streamPaymentAddress, setStreamPaymentAddress] = React.useState("");
  const { topUp: topUpAction } = useStreamActions(streamPaymentAddress);

  const syncSettings = React.useCallback(() => {
    const settings = loadSettings();
    setDisplayCurrency(
      settings.display_currency === "token" ? "token" : "fiat",
    );
    setShowEnded(!!settings.show_ended_streams);
    setStreamPaymentAddress(
      (
        settings.stream_payment_address ||
        getRequestorRuntimeConfig().streamPaymentAddress ||
        ""
      ).trim(),
    );
  }, []);

  const syncRentals = React.useCallback(() => {
    setRentals(loadRentals());
  }, []);

  React.useEffect(() => {
    setMounted(true);
    syncSettings();
    syncRentals();
  }, [syncRentals, syncSettings]);

  React.useEffect(() => {
    const timer = window.setInterval(
      () => setNowSec(Math.floor(Date.now() / 1000)),
      1000,
    );
    return () => window.clearInterval(timer);
  }, []);

  React.useEffect(() => {
    if (!mounted) return;

    const onSettings = () => syncSettings();
    const onRentals = () => syncRentals();

    window.addEventListener("requestor_settings_changed", onSettings);
    window.addEventListener("requestor_rentals_changed", onRentals);
    window.addEventListener("storage", onSettings);
    window.addEventListener("storage", onRentals);
    return () => {
      window.removeEventListener("requestor_settings_changed", onSettings);
      window.removeEventListener("requestor_rentals_changed", onRentals);
      window.removeEventListener("storage", onSettings);
      window.removeEventListener("storage", onRentals);
    };
  }, [mounted, syncRentals, syncSettings]);

  const streamRentals = React.useMemo(
    () =>
      rentals.filter((rental) => rental.stream_id),
    [rentals],
  );
  const liveStreams = usePaymentStreamsLive(
    streamPaymentAddress,
    streamRentals,
  );

  React.useEffect(() => {
    if (!mounted) return;
    if (!streamRentals.length) {
      setRows([]);
      setError(null);
      setRefreshing(false);
      return;
    }
    if (!streamPaymentAddress) {
      setRows([]);
      setError("StreamPayment address not configured in Settings.");
      setRefreshing(false);
      return;
    }

    const entries = streamRentals.map((rental) =>
      rental.stream_id ? liveStreams.entries[String(rental.stream_id)] : null,
    );
    const loadedEntries = entries.filter(Boolean);
    if (loadedEntries.length < streamRentals.length) {
      setRows(null);
      return;
    }

    const nextRows = loadedEntries.flatMap((entry) => {
      if (!entry || !entry.ok) return [];
      return [
        {
          r: entry.rental,
          chain: entry.data.chain,
          tokenSymbol: entry.data.tokenSymbol,
          tokenDecimals: entry.data.tokenDecimals,
          usdPrice: entry.data.usdPrice,
        },
      ];
    });
    const firstEntryError = loadedEntries.find(
      (entry) => entry && !entry.ok,
    );
    setRows(nextRows);
    setError(
      liveStreams.error ||
        (firstEntryError && !firstEntryError.ok ? firstEntryError.error : null),
    );
    setRefreshing(false);
  }, [
    liveStreams.entries,
    liveStreams.error,
    mounted,
    streamRentals,
    streamPaymentAddress,
  ]);

  React.useEffect(() => {
    const off = onPricesUpdated(() => {
      setRows((current) => {
        if (!current) return current;
        return current.map((row) => {
          const symbol = (row.tokenSymbol || "").toUpperCase();
          const usdPrice =
            symbol === "ETH" || symbol === "WETH"
              ? getPriceUSD("ETH")
              : symbol === "GLM" || symbol === "GNT"
                ? getPriceUSD("GLM")
                : null;
          return { ...row, usdPrice };
        });
      });
    });
    return () => {
      off();
    };
  }, []);

  const active = React.useMemo(
    () => (rows || []).filter((row) => !isEndedStream(row, nowSec)),
    [nowSec, rows],
  );
  const ended = React.useMemo(
    () => (rows || []).filter((row) => isEndedStream(row, nowSec)),
    [nowSec, rows],
  );

  const updateDisplayCurrency = (value: DisplayCurrency) => {
    setDisplayCurrency(value);
    saveSettings({ display_currency: value });
  };

  const updateShowEnded = (value: boolean) => {
    setShowEnded(value);
    saveSettings({ show_ended_streams: value });
  };

  const refreshStreams = React.useCallback(async (_options?: { background?: boolean }) => {
    setRefreshing(true);
    await liveStreams.refresh();
  }, [liveStreams.refresh]);

  const topUp = async (row: StreamRow, seconds: number) => {
    const streamId = String(row.r.stream_id);
    if (!streamId || !streamPaymentAddress) return;

    setBusy((current) => ({ ...current, [streamId]: true }));
    try {
      await topUpAction(
        BigInt(streamId),
        row.chain.token,
        row.chain.ratePerSecond,
        seconds,
      );
      show("Top-up sent");
      await refreshStreams();
    } catch (topUpError) {
      show(getPaymentNetworkErrorMessage(topUpError));
    } finally {
      setBusy((current) => ({ ...current, [streamId]: false }));
    }
  };

  return {
    active,
    busy,
    displayCurrency,
    ended,
    error,
    hasConfiguredStreams: streamRentals.length > 0,
    hasRows: !!rows && rows.length > 0,
    mounted,
    nowSec,
    paymentMessage,
    paymentReady,
    refreshing,
    rows,
    showEnded,
    topUp,
    updateDisplayCurrency,
    updateShowEnded,
    refreshStreams,
  };
}
