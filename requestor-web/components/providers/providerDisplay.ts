import type { ProviderAd } from "../../lib/api";
import { countryFullName } from "../../lib/intl";

export type ProviderSpec = {
  cpu?: number;
  memory?: number;
  storage?: number;
};

export function shortProviderId(id: string) {
  return id.length > 13 ? `${id.slice(0, 6)}...${id.slice(-4)}` : id;
}

export function providerLocation(provider: ProviderAd) {
  const code = provider.country || "";
  return {
    code,
    name: code ? countryFullName(code) : "Unknown",
  };
}

export function providerPlatform(provider: ProviderAd) {
  const value = String(provider.platform || "linux").toLowerCase();
  if (value.includes("win")) return "Windows";
  return "Linux";
}

export function estimateSpec(spec: ProviderSpec) {
  return {
    cpu: spec.cpu && spec.cpu > 0 ? spec.cpu : 1,
    memory: spec.memory && spec.memory > 0 ? spec.memory : 2,
    storage: spec.storage && spec.storage >= 10 ? spec.storage : 20,
  };
}

export function providerMatchesSearch(provider: ProviderAd, query: string) {
  const normalized = query.trim().toLowerCase();
  if (!normalized) return true;
  const location = providerLocation(provider);
  return [
    provider.provider_id,
    provider.ip_address,
    provider.country,
    location.name,
    provider.platform,
  ]
    .filter(Boolean)
    .some((value) => String(value).toLowerCase().includes(normalized));
}
