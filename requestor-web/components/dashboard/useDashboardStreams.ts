"use client";

import React from "react";
import { loadSettings, type Rental } from "../../lib/api";
import { getRequestorRuntimeConfig } from "../../lib/runtimeConfig";
import { fetchStreamWithMeta, isTerminatedStream } from "../../lib/streams";
import type { DashboardStreamRow } from "./DashboardTables";

function tokenAmount(value: bigint, decimals: number) {
  return Number(value) / 10 ** decimals;
}

export function useDashboardStreams(rentals: Rental[]) {
  const [rows, setRows] = React.useState<DashboardStreamRow[]>([]);
  const [loadedStreamKey, setLoadedStreamKey] = React.useState("");
  const [totalSpent, setTotalSpent] = React.useState({
    token: "GLM",
    tokenValue: 0,
    usdValue: 0,
    monthlyBurn: 0,
    spendSeries: zeroSpendSeries(),
  });
  const streamKey = rentals.map((rental) => `${rental.vm_id}:${rental.stream_id || ""}`).join("|");

  React.useEffect(() => {
    let cancelled = false;
    const streamRentals = rentals.filter((rental) => rental.stream_id);
    const spAddr = (
      loadSettings().stream_payment_address ||
      getRequestorRuntimeConfig().streamPaymentAddress ||
      ""
    ).trim();

    if (!streamRentals.length) {
      setRows([]);
      setTotalSpent({
        token: "GLM",
        tokenValue: 0,
        usdValue: 0,
        monthlyBurn: 0,
        spendSeries: zeroSpendSeries(),
      });
      setLoadedStreamKey(streamKey);
      return;
    }

    async function loadRows() {
      const loaded = await Promise.all(
        streamRentals.map(async (rental) => loadStreamRow(rental, spAddr)),
      );

      if (cancelled) return;
      const token = loaded[0]?.row.tokenSymbol || "GLM";
      setRows(loaded.map((item) => item.row));
      setTotalSpent({
        token,
        tokenValue: loaded.reduce((sum, item) => sum + item.spent, 0),
        usdValue: loaded.reduce((sum, item) => sum + item.spentUsd, 0),
        monthlyBurn: loaded.reduce((sum, item) => sum + item.monthlyBurn, 0),
        spendSeries: buildSpendSeries(loaded),
      });
      setLoadedStreamKey(streamKey);
    }

    loadRows();
    return () => {
      cancelled = true;
    };
  }, [streamKey]);

  return {
    rows,
    totalSpent,
    isInitialLoading: streamKey !== "" && loadedStreamKey !== streamKey,
  };
}

async function loadStreamRow(rental: Rental, spAddr: string) {
  if (!spAddr) return unavailableStreamRow(rental);

  try {
    const data = await fetchStreamWithMeta(spAddr, BigInt(rental.stream_id!));
    const decimals = data.tokenDecimals || 18;
    const rps = tokenAmount(data.chain.ratePerSecond, decimals);
    const remainingSeconds = Number(data.remaining);
    const remainingTokens = Math.max(0, rps * remainingSeconds);
    const hourlyTokens = rps * 3600;
    const spent = tokenAmount(data.chain.withdrawn, decimals);
    return {
      row: {
        rental,
        remainingSeconds,
        spentSoFar: spent.toFixed(2),
        remainingBalance: remainingTokens.toFixed(2),
        hourlyRate: hourlyTokens.toFixed(2),
        tokenSymbol: data.tokenSymbol,
        status: isTerminatedStream(data.chain) ? "Terminated" : "Active",
      } satisfies DashboardStreamRow,
      spent,
      spentUsd: data.usdPrice == null ? 0 : spent * data.usdPrice,
      monthlyBurn: hourlyTokens * 730,
      startedAt: Number(rental.created_at || 0) * 1000 || monthStartMs(),
    };
  } catch {
    return unavailableStreamRow(rental);
  }
}

function unavailableStreamRow(rental: Rental) {
  return {
    row: {
      rental,
      remainingSeconds: null,
      spentSoFar: null,
      remainingBalance: null,
      hourlyRate: null,
      tokenSymbol: "GLM",
      status: "Unavailable",
    } satisfies DashboardStreamRow,
    spent: 0,
    spentUsd: 0,
    monthlyBurn: 0,
    startedAt: Number(rental.created_at || 0) * 1000 || monthStartMs(),
  };
}

type LoadedStream = Awaited<ReturnType<typeof loadStreamRow>>;

function zeroSpendSeries() {
  return Array.from({ length: 16 }, () => 0);
}

function monthStartMs() {
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), 1).getTime();
}

function buildSpendSeries(streams: LoadedStream[]) {
  const pointCount = 16;
  const nowMs = Date.now();
  const startMs = monthStartMs();
  const duration = Math.max(1, nowMs - startMs);

  return Array.from({ length: pointCount }, (_, index) => {
    const pointMs = startMs + (duration * index) / Math.max(1, pointCount - 1);
    return streams.reduce((sum, stream) => {
      if (stream.spent <= 0) return sum;
      const streamStart = Math.max(startMs, stream.startedAt);
      if (pointMs <= streamStart) return sum;
      const streamDuration = Math.max(1, nowMs - streamStart);
      const progress = Math.min(1, (pointMs - streamStart) / streamDuration);
      return sum + stream.spent * progress;
    }, 0);
  });
}
