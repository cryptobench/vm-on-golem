import type { ProviderAd } from "./api";
import { countriesFromProviders } from "./discovery";

export function listCountries(providers: ProviderAd[]) {
  return countriesFromProviders(providers);
}
