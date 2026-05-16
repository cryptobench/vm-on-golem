import { getRequestorRuntimeConfig } from "./runtimeConfig";

export function providerUrl(providerEndpointUrl: string, path: string): string {
  return `${normalizeProviderEndpoint(providerEndpointUrl)}${path}`;
}

export function normalizeProviderEndpoint(endpointUrl: string): string {
  return requireProviderEndpoint(endpointUrl).replace(/\/$/, "");
}

export function requireProviderEndpoint(endpointUrl: unknown): string {
  const value = typeof endpointUrl === "string" ? endpointUrl.trim() : "";
  if (!isUsableProviderEndpoint(value)) {
    throw new Error("Provider endpoint unavailable");
  }
  return value;
}

export function isUsableProviderEndpoint(endpointUrl: unknown): endpointUrl is string {
  if (typeof endpointUrl !== "string" || !endpointUrl.trim()) return false;
  try {
    const url = new URL(endpointUrl);
    if (url.protocol === "https:") return true;
    return (
      url.protocol === "http:" &&
      getRequestorRuntimeConfig().golemEnvironment === "development"
    );
  } catch {
    return false;
  }
}

