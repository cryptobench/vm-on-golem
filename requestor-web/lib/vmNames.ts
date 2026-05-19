const FALLBACK_PROVIDER_SUFFIX = "node";

export function generateVmName(providerId: string, suffix = randomNameSuffix()): string {
  const providerSuffix = providerId
    .toLowerCase()
    .replace(/[^a-z0-9]/g, "")
    .slice(-4);
  return `vm-${providerSuffix || FALLBACK_PROVIDER_SUFFIX}-${suffix}`;
}

function randomNameSuffix(): string {
  if (!globalThis.crypto?.getRandomValues) {
    throw new Error("crypto.getRandomValues is required to generate VM names");
  }
  const bytes = new Uint8Array(3);
  globalThis.crypto.getRandomValues(bytes);
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
}
