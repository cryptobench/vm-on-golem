export type LocalDateTimeOptions = Intl.DateTimeFormatOptions;

const DATE_TIME_OPTIONS: Intl.DateTimeFormatOptions = {
  month: "short",
  day: "numeric",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
};

const DATE_OPTIONS: Intl.DateTimeFormatOptions = {
  month: "short",
  day: "numeric",
  year: "numeric",
};

const TIME_OPTIONS: Intl.DateTimeFormatOptions = {
  hour: "2-digit",
  minute: "2-digit",
};

const TIMEZONE_PATTERN = /(?:Z|[+-]\d{2}:?\d{2})$/i;

export function parseAbsoluteTimestamp(value: string | null | undefined) {
  if (!value || !TIMEZONE_PATTERN.test(value)) return null;
  const timestamp = Date.parse(value);
  return Number.isFinite(timestamp) ? timestamp : null;
}

export function formatLocalDateTime(
  value: string | number | Date | null | undefined,
  options: LocalDateTimeOptions = DATE_TIME_OPTIONS,
) {
  const date = localDate(value);
  if (!date) return null;
  return new Intl.DateTimeFormat(undefined, options).format(date);
}

export function formatLocalDate(value: string | number | Date | null | undefined) {
  return formatLocalDateTime(value, DATE_OPTIONS);
}

export function formatLocalTime(value: string | number | Date | null | undefined) {
  return formatLocalDateTime(value, TIME_OPTIONS);
}

export function formatUnixSecondsDateTime(value: number | bigint | null | undefined) {
  const seconds = Number(value);
  if (!Number.isFinite(seconds) || seconds <= 0) return null;
  return formatLocalDateTime(seconds * 1000);
}

function localDate(value: string | number | Date | null | undefined) {
  if (value == null) return null;
  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : value;
  }
  const timestamp =
    typeof value === "string" ? parseAbsoluteTimestamp(value) : value;
  if (timestamp == null || !Number.isFinite(timestamp)) return null;
  const date = new Date(timestamp);
  return Number.isNaN(date.getTime()) ? null : date;
}
