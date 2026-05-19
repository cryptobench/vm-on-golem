import type { DurationPreset } from "./types";

export const RENT_STEPS = [
  "Choose specs",
  "Rental duration",
  "Access",
  "Review",
] as const;

export type RentDurationPreset = DurationPreset | "24h";

export const DURATION_OPTIONS: Array<{
  preset: Exclude<RentDurationPreset, "custom">;
  label: string;
  seconds: number;
}> = [
  { preset: "24h", label: "24 hours", seconds: 24 * 3600 },
  { preset: "1w", label: "7 days", seconds: 7 * 24 * 3600 },
  { preset: "2w", label: "14 days", seconds: 14 * 24 * 3600 },
  { preset: "30d", label: "30 days", seconds: 30 * 24 * 3600 },
];
