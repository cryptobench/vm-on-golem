import type { Rental } from "./api";

type AccessLike = {
  ssh_host?: string | null;
  ssh_port?: number | string | null;
};

type ProviderLike = {
  ip_address?: string | null;
  endpoint_url?: string | null;
};

function clean(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

export function endpointHost(endpointUrl?: string | null): string | null {
  const value = clean(endpointUrl);
  if (!value) return null;
  try {
    return new URL(value).hostname || null;
  } catch {
    return null;
  }
}

export function providerPublicHost({
  access,
  provider,
  rental,
}: {
  access?: unknown;
  provider?: unknown;
  rental: Pick<Rental, "provider_endpoint_url" | "provider_ip">;
}): string | null {
  const accessInfo = access as AccessLike | null | undefined;
  const providerInfo = provider as ProviderLike | null | undefined;
  return (
    clean(accessInfo?.ssh_host) ||
    clean(providerInfo?.ip_address) ||
    endpointHost(providerInfo?.endpoint_url) ||
    endpointHost(rental.provider_endpoint_url) ||
    clean(rental.provider_ip) ||
    null
  );
}

export function sshPort({
  access,
  rental,
}: {
  access?: unknown;
  rental: Pick<Rental, "ssh_port">;
}): number | null {
  const accessInfo = access as AccessLike | null | undefined;
  const value = accessInfo?.ssh_port ?? rental.ssh_port;
  const port = Number(value);
  return Number.isFinite(port) && port > 0 ? port : null;
}

export function sshEndpointLabel({
  access,
  provider,
  rental,
}: {
  access?: unknown;
  provider?: unknown;
  rental: Pick<Rental, "provider_endpoint_url" | "provider_ip" | "ssh_port">;
}): string {
  const host = providerPublicHost({ access, provider, rental });
  const port = sshPort({ access, rental });
  if (host && port) return `${host}:${port}`;
  return "-";
}
