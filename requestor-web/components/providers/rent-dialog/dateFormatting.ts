import type { SSHKey } from "../../../lib/api";
import { formatLocalDate } from "../../../lib/time";

export function formatDurationLabel(seconds: number) {
  if (!seconds) return "Duration required";
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const parts = [];
  if (days) parts.push(`${days}d`);
  if (hours) parts.push(`${hours}h`);
  if (minutes) parts.push(`${minutes}m`);
  return parts.join(" ") || "1h";
}

export function formatDate(date: Date) {
  return formatLocalDate(date) ?? "Unavailable";
}

export function fingerprintForKey(key: SSHKey | null, fallback: string) {
  const source = key?.value || key?.public_key || fallback;
  const body = source.split(" ")[1] || source;
  if (!body) return "Unavailable";
  const compact = body.replace(/\s+/g, "");
  if (compact.length <= 36) return compact;
  return `SHA256:${compact.slice(0, 24)}...${compact.slice(-12)}`;
}

export function formatGlm(value?: number) {
  if (value == null || Number.isNaN(value)) return "0";
  if (value >= 100) return value.toFixed(2);
  if (value >= 1) return value.toFixed(4);
  return value.toFixed(6);
}
