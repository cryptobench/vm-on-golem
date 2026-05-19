export {
  formatLocalDate,
  formatLocalDateTime,
  formatLocalTime,
  formatUnixSecondsDateTime,
  parseAbsoluteTimestamp,
} from "@golem/ui";

export function parseHumanDuration(input: string): number {
  const value = input.trim().toLowerCase();
  if (!value) return 0;
  const match = value.match(/^(\d+(?:\.\d+)?)(s|m|h|d)?$/);
  if (!match) return 0;
  const amount = Number(match[1]);
  const unit = match[2] || "s";
  const multipliers: Record<string, number> = { s: 1, m: 60, h: 3600, d: 86400 };
  return Math.floor(amount * multipliers[unit]);
}
