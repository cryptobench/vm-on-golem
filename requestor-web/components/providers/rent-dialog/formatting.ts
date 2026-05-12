import type { ProviderAd } from "../../../lib/api";
import type { PriceLine, RentSpec } from "./types";

const HOURS_PER_MONTH = 730;

export function clampSpec(spec: Partial<RentSpec>, provider: ProviderAd): RentSpec {
  return {
    cpu: clampNumber(spec.cpu || 1, 1, provider.resources.cpu),
    memory: clampNumber(spec.memory || 2, 1, provider.resources.memory),
    storage: clampNumber(spec.storage || 20, 1, provider.resources.storage),
  };
}

export function priceLine(usd?: number, glm?: number, preferToken = true): PriceLine {
  const usdText = usd == null ? undefined : formatUsd(usd);
  const glmText = glm == null ? undefined : `${formatToken(glm)} GLM`;

  if (preferToken && glmText) return { primary: glmText, secondary: usdText };
  if (usdText) return { primary: usdText, secondary: glmText };
  return { primary: "Unavailable" };
}

export function hourlyGlm(glmPerMonth?: number) {
  return glmPerMonth == null ? undefined : glmPerMonth / HOURS_PER_MONTH;
}

export function durationTotal(monthlyValue: number | undefined, seconds: number) {
  if (monthlyValue == null || seconds <= 0) return undefined;
  return (monthlyValue / HOURS_PER_MONTH) * (seconds / 3600);
}

export function formatUsd(value: number) {
  return `$${value.toFixed(value < 1 ? 4 : 2)}`;
}

function formatToken(value: number) {
  if (value >= 100) return value.toFixed(2);
  if (value >= 1) return value.toFixed(4);
  return value.toFixed(6);
}

function clampNumber(value: number, min: number, max: number) {
  const safeMax = Math.max(min, Math.floor(max || min));
  return Math.min(Math.max(Math.floor(value), min), safeMax);
}
