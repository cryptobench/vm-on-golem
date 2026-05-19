import type { UpdateProviderPricing, VMResources } from "../../lib/types";

export function subtractResources(total: VMResources, used: VMResources): VMResources {
  return {
    cpu: Math.max(0, total.cpu - used.cpu),
    memory: Math.max(0, total.memory - used.memory),
    storage: Math.max(0, total.storage - used.storage),
  };
}

export function formatResources(resources: VMResources) {
  return `${resources.cpu} cores / ${resources.memory} GB / ${resources.storage} GB`;
}

export function sameResources(a: VMResources, b: VMResources) {
  return a.cpu === b.cpu && a.memory === b.memory && a.storage === b.storage;
}

export function clampWhole(value: number, min: number, max: number) {
  const numeric = Number.isFinite(value) ? value : min;
  return Math.min(Math.max(Math.round(numeric), min), Math.max(min, max));
}

export function calculateEarnings(
  resources: VMResources,
  pricing: UpdateProviderPricing,
) {
  return (
    resources.cpu * pricing.usd_per_core_month +
    resources.memory * pricing.usd_per_gb_ram_month +
    resources.storage * pricing.usd_per_gb_storage_month
  );
}

export function messageFromError(error: unknown) {
  return error instanceof Error ? error.message : String(error);
}
