import type { Rental } from "../../lib/api";
import type { ChainStream } from "../../lib/streams";

export type DisplayCurrency = "fiat" | "token";

export type StreamRow = {
  r: Rental;
  chain: ChainStream;
  tokenSymbol: string;
  tokenDecimals: number;
  usdPrice: number | null;
};

export type StreamStatusKind =
  | "active"
  | "needs-top-up"
  | "out-of-funds"
  | "halted";

export type TokenTotal = {
  symbol: string;
  value: number;
};

export function remainingSeconds(row: StreamRow, nowSec: number) {
  if (row.chain.halted) return 0;
  return Math.max(0, Number(row.chain.stopTime || 0n) - nowSec);
}

export function tokenScale(row: StreamRow) {
  return 10 ** (row.tokenDecimals || 18);
}

export function hourlyTokenRate(row: StreamRow) {
  return (Number(row.chain.ratePerSecond) / tokenScale(row)) * 3600;
}

export function depositedTokenBalance(row: StreamRow) {
  return Number(row.chain.deposit) / tokenScale(row);
}

export function remainingTokenBalance(row: StreamRow, nowSec: number) {
  return (Number(row.chain.ratePerSecond) / tokenScale(row)) * remainingSeconds(row, nowSec);
}

export function spentTokenBalance(row: StreamRow, nowSec: number) {
  const ratePerSecond = Number(row.chain.ratePerSecond) / tokenScale(row);
  const startTime = Number(row.chain.startTime || 0n);
  const stopTime = Number(row.chain.stopTime || 0n);
  const deposit = depositedTokenBalance(row);
  const effectiveTime = row.chain.halted
    ? stopTime
    : Math.min(nowSec, stopTime);
  const elapsedSeconds = Math.max(0, effectiveTime - startTime);
  return Math.max(0, Math.min(deposit, elapsedSeconds * ratePerSecond));
}

export function streamRunwayPercent(row: StreamRow, nowSec: number) {
  const ratePerSecond = Number(row.chain.ratePerSecond) / tokenScale(row);
  const deposit = Number(row.chain.deposit) / tokenScale(row);
  if (row.chain.halted || ratePerSecond <= 0 || deposit <= 0) return 0;
  const totalSeconds = Math.max(1, Math.floor(deposit / ratePerSecond));
  return Math.max(0, Math.min(100, (remainingSeconds(row, nowSec) / totalSeconds) * 100));
}

export function streamStatus(row: StreamRow, nowSec: number): StreamStatusKind {
  if (row.chain.halted) return "halted";
  const remaining = remainingSeconds(row, nowSec);
  if (remaining <= 0 || remainingTokenBalance(row, nowSec) <= 0) return "out-of-funds";
  if (remaining < 3600) return "needs-top-up";
  return "active";
}

export function isEndedStream(row: StreamRow, nowSec: number) {
  const status = streamStatus(row, nowSec);
  return status === "halted" || status === "out-of-funds";
}

export function formatTokenAmount(value: number, symbol: string, maxDigits = 2) {
  return `${formatNumber(value, maxDigits)} ${symbol || "TOKEN"}`;
}

export function formatFiat(value: number, maxDigits = 2) {
  return `$${new Intl.NumberFormat("en", {
    maximumFractionDigits: maxDigits,
    minimumFractionDigits: 2,
  }).format(value)}`;
}

export function formatNumber(value: number, maxDigits = 2) {
  return new Intl.NumberFormat("en", {
    maximumFractionDigits: maxDigits,
    minimumFractionDigits: value > 0 && value < 1 ? Math.min(2, maxDigits) : 0,
  }).format(value);
}

export function compactId(value?: string | number | null) {
  if (value == null || value === "") return "-";
  const text = String(value);
  if (text.length <= 13) return text;
  return `${text.slice(0, 6)}...${text.slice(-4)}`;
}

export function tokenTotals(
  rows: StreamRow[],
  valueForRow: (row: StreamRow) => number,
) {
  const totals = new Map<string, number>();
  for (const row of rows) {
    const symbol = row.tokenSymbol || "TOKEN";
    totals.set(symbol, (totals.get(symbol) || 0) + valueForRow(row));
  }
  return Array.from(totals, ([symbol, value]) => ({ symbol, value }));
}

export function fiatTotal(
  rows: StreamRow[],
  valueForRow: (row: StreamRow) => number,
) {
  return rows.reduce((sum, row) => {
    if (row.usdPrice == null) return sum;
    return sum + valueForRow(row) * row.usdPrice;
  }, 0);
}
