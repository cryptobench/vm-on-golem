"use client";

import React from "react";
import { useProjects } from "../../context/ProjectsContext";
import { useWallet } from "../../context/WalletContext";
import { useStreamActions } from "../../hooks/useStreamActions";
import {
  loadRentals,
  loadSettings,
  saveSettings,
  type Rental,
} from "../../lib/api";
import { getPaymentNetworkErrorMessage } from "../../lib/chain";
import { getPriceUSD, onPricesUpdated } from "../../lib/prices";
import { fetchStreamWithMeta } from "../../lib/streams";
import { useToast } from "@golem/ui";
import {
  isEndedStream,
  type DisplayCurrency,
  type StreamRow,
} from "../../components/streams/streamModel";

const STREAM_REFRESH_MS = 15000;

export function useStreamsScreen() {
  const { show } = useToast();
  const { paymentReady, paymentMessage } = useWallet();
  const { activeId: activeProjectId } = useProjects();
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
        process.env.NEXT_PUBLIC_STREAM_PAYMENT_ADDRESS ||
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

  const projectStreamRentals = React.useMemo(
    () =>
      rentals.filter(
        (rental) =>
          rental.stream_id &&
          (rental.project_id || "default") === activeProjectId,
      ),
    [activeProjectId, rentals],
  );

  const loadStreams = React.useCallback(
    async ({ background = false }: { background?: boolean } = {}) => {
      if (!mounted) return;
      if (!projectStreamRentals.length) {
        setRows([]);
        setError(null);
        setRefreshing(false);
        return;
      }
      if (!streamPaymentAddress) {
        setRows([]);
        setError("StreamPayment address not configured in Settings.");
        return;
      }

      if (!background) setRows(null);
      setRefreshing(background);
      setError(null);

      try {
        const results = await Promise.all(
          projectStreamRentals.map(async (rental) => {
            try {
              const data = await fetchStreamWithMeta(
                streamPaymentAddress,
                BigInt(rental.stream_id!),
              );
              return {
                ok: true as const,
                row: {
                  r: rental,
                  chain: data.chain,
                  tokenSymbol: data.tokenSymbol,
                  tokenDecimals: data.tokenDecimals,
                  usdPrice: data.usdPrice,
                },
              };
            } catch (streamError) {
              return {
                ok: false as const,
                message: getPaymentNetworkErrorMessage(streamError),
              };
            }
          }),
        );

        const nextRows = results.flatMap((result) =>
          result.ok ? [result.row] : [],
        );
        const firstError = results.find((result) => !result.ok);
        setRows(nextRows);
        setError(firstError && !firstError.ok ? firstError.message : null);
      } catch (loadError) {
        setError(getPaymentNetworkErrorMessage(loadError));
        setRows([]);
      } finally {
        setRefreshing(false);
      }
    },
    [mounted, projectStreamRentals, streamPaymentAddress],
  );

  React.useEffect(() => {
    if (!mounted) return;
    loadStreams();
  }, [loadStreams, mounted]);

  React.useEffect(() => {
    if (!mounted) return;
    const timer = window.setInterval(() => {
      loadStreams({ background: true });
    }, STREAM_REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [loadStreams, mounted]);

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

  const refreshOne = async (streamId: string) => {
    const current = rows || [];
    const index = current.findIndex(
      (row) => String(row.r.stream_id) === streamId,
    );
    if (index < 0) return;

    const data = await fetchStreamWithMeta(streamPaymentAddress, BigInt(streamId));
    const next = [...current];
    next[index] = {
      ...next[index],
      chain: data.chain,
      tokenSymbol: data.tokenSymbol,
      tokenDecimals: data.tokenDecimals,
      usdPrice: data.usdPrice,
    };
    setRows(next);
  };

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
      await refreshOne(streamId);
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
    hasConfiguredStreams: projectStreamRentals.length > 0,
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
    refreshStreams: loadStreams,
  };
}
