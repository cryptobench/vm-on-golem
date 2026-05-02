import type { AdsConfig } from "./api";
import { fetchAllProviders } from "./api";

export async function listCountries(ads: AdsConfig) {
  const providers = await fetchAllProviders(ads);
  return Array.from(
    new Set(providers.map((provider) => provider.country).filter(Boolean) as string[]),
  ).sort();
}
