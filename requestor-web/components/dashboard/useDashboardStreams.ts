"use client";

import { loadSettings, type Rental } from "../../lib/api";
import {
  usePaymentStreamsLive,
  type PaymentStreamData,
} from "../../lib/paymentStreamLive";
import { getRequestorRuntimeConfig } from "../../lib/runtimeConfig";
import { isTerminatedStream } from "../../lib/streams";
import type { DashboardStreamRow } from "./DashboardTables";

function tokenAmount(value: bigint, decimals: number) {
  return Number(value) / 10 ** decimals;
}

export function useDashboardStreams(rentals: Rental[]) {
  const streamRentals = rentals.filter((rental) => rental.stream_id);
  const spAddr = (
    loadSettings().stream_payment_address ||
    getRequestorRuntimeConfig().streamPaymentAddress ||
    ""
  ).trim();
  const liveStreams = usePaymentStreamsLive(spAddr, rentals);

  const emptyTotalSpent = {
    token: "GLM",
    tokenValue: 0,
    usdValue: 0,
    monthlyBurn: 0,
    spendSeries: zeroSpendSeries(),
  };
  if (!streamRentals.length) {
    return {
      rows: [],
      totalSpent: emptyTotalSpent,
      isInitialLoading: false,
    };
  }

  if (!spAddr || liveStreams.error) {
    return {
      rows: streamRentals.map((rental) => unavailableStreamRow(rental).row),
      totalSpent: emptyTotalSpent,
      isInitialLoading: false,
    };
  }

  const entries = streamRentals.map((rental) =>
    rental.stream_id ? liveStreams.entries[String(rental.stream_id)] : null,
  );
  if (entries.some((entry) => !entry)) {
    return {
      rows: [],
      totalSpent: emptyTotalSpent,
      isInitialLoading: true,
    };
  }

  const loaded = entries.map((entry, index) =>
    entry!.ok
      ? streamRowFromLiveData(streamRentals[index], entry!.data)
      : unavailableStreamRow(streamRentals[index]),
  );
  const token = loaded[0]?.row.tokenSymbol || "GLM";
  return {
    rows: loaded.map((item) => item.row),
    totalSpent: {
      token,
      tokenValue: loaded.reduce((sum, item) => sum + item.spent, 0),
      usdValue: loaded.reduce((sum, item) => sum + item.spentUsd, 0),
      monthlyBurn: loaded.reduce((sum, item) => sum + item.monthlyBurn, 0),
      spendSeries: buildSpendSeries(loaded),
    },
    isInitialLoading: false,
  };
}

function streamRowFromLiveData(rental: Rental, data: PaymentStreamData) {
  const decimals = data.tokenDecimals || 18;
  const rps = tokenAmount(data.chain.providerRatePerSecond, decimals);
  const donationMultiplier = 1 + Number(data.chain.donationBps || 0) / 10_000;
  const remainingSeconds = Number(data.remaining);
  const remainingTokens = Math.max(0, rps * donationMultiplier * remainingSeconds);
  const hourlyTokens = rps * donationMultiplier * 3600;
  const spent = tokenAmount(
    data.chain.providerWithdrawn + data.chain.donationWithdrawn,
    decimals,
  );
  const terminated = isTerminatedStream(data.chain);
  return {
    row: {
      rental,
      remainingSeconds,
      spentSoFar: spent.toFixed(2),
      remainingBalance: remainingTokens.toFixed(2),
      hourlyRate: hourlyTokens.toFixed(2),
      tokenSymbol: data.tokenSymbol,
      status: terminated ? "Terminated" : "Active",
    } satisfies DashboardStreamRow,
    spent,
    spentUsd: data.usdPrice == null ? 0 : spent * data.usdPrice,
    monthlyBurn: terminated ? 0 : hourlyTokens * 730,
    startedAt: Number(rental.created_at || 0) * 1000 || monthStartMs(),
  };
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

type LoadedStream =
  | ReturnType<typeof streamRowFromLiveData>
  | ReturnType<typeof unavailableStreamRow>;

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
