import { formatLocalDateTime } from "@golem/ui";
import type { VMStatus } from "./types";

export const EMPTY_VALUE = "--";

export function formatCurrency(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) return EMPTY_VALUE;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }).format(value);
}

export function formatGlm(value: number | null | undefined, digits = 2) {
  if (value == null || Number.isNaN(value)) return EMPTY_VALUE;
  return `${new Intl.NumberFormat("en-US", {
    maximumFractionDigits: digits,
  }).format(value)} GLM`;
}

export function formatPercent(value: number | null | undefined, digits = 1) {
  if (value == null || Number.isNaN(value)) return EMPTY_VALUE;
  return `${value.toFixed(digits)}%`;
}

export function formatBytes(value: unknown) {
  const bytes = Number(value);
  if (!Number.isFinite(bytes)) return EMPTY_VALUE;
  const units = ["B", "KB", "MB", "GB", "TB"];
  let scaled = bytes;
  let index = 0;
  while (scaled >= 1024 && index < units.length - 1) {
    scaled /= 1024;
    index += 1;
  }
  return `${scaled.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

export function formatDateTime(value: string | null | undefined) {
  return formatLocalDateTime(value) ?? EMPTY_VALUE;
}

export function formatDuration(seconds: number | null | undefined) {
  if (seconds == null || !Number.isFinite(seconds)) return EMPTY_VALUE;
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (days > 0) return `${days}d ${hours}h ${minutes}m`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}

export function shortAddress(value: string | null | undefined) {
  if (!value) return EMPTY_VALUE;
  if (value.length <= 12) return value;
  return `${value.slice(0, 6)}...${value.slice(-4)}`;
}

export function weiToToken(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) return null;
  return value / 1_000_000_000_000_000_000;
}

export function titleCase(value: string | null | undefined) {
  if (!value) return EMPTY_VALUE;
  return value
    .split(/[_-]/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function vmStatusLabel(status: VMStatus) {
  return titleCase(status);
}
