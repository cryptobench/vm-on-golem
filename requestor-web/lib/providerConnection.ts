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

export function sshEndpointLabel({
  access,
}: {
  access?: unknown;
  provider?: unknown;
  rental: Pick<Rental, "provider_endpoint_url" | "provider_ip" | "ssh_port">;
}): string {
  const accessInfo = access as AccessLike | null | undefined;
  const host = clean(accessInfo?.ssh_host);
  const portValue = Number(accessInfo?.ssh_port);
  const port = Number.isFinite(portValue) && portValue > 0 ? portValue : null;
  if (host && port) return `${host}:${port}`;
  return "-";
}
