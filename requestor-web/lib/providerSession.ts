"use client";

import { getPaymentsSigner } from "./walletClient";
import { providerUrl } from "./providerEndpoint";

type ProviderInfoResponse = {
  provider_id: string;
};

type RequestorSessionResponse = {
  access_token: string;
  expires_at: number;
  requestor_address: string;
  vm_id: string;
};

const CACHE_KEY = "golem_provider_vm_sessions_v1";
const EXPIRY_SKEW_SECONDS = 30;

type CachedSession = {
  token: string;
  expiresAt: number;
  requestor: string;
};

export async function getProviderVmSession(
  providerEndpointUrl: string,
  vmId: string,
): Promise<string> {
  const signer = await getPaymentsSigner();
  const requestor = await signer.getAddress();
  const cacheKey = sessionKey(providerEndpointUrl, vmId, requestor);
  const cached = readSession(cacheKey);
  const now = Math.floor(Date.now() / 1000);
  if (cached && cached.expiresAt - EXPIRY_SKEW_SECONDS > now) {
    return cached.token;
  }

  const provider = await fetchProviderInfo(providerEndpointUrl);
  const deadline = now + 900;
  const nonce = newNonce();
  const scope = "vm";
  const signature = await signer.signTypedData(
    { name: "GolemProviderSession", version: "1" },
    {
      ProviderSession: [
        { name: "provider", type: "address" },
        { name: "requestor", type: "address" },
        { name: "vmId", type: "string" },
        { name: "scope", type: "string" },
        { name: "nonce", type: "string" },
        { name: "deadline", type: "uint256" },
      ],
    },
    {
      provider: provider.provider_id,
      requestor,
      vmId,
      scope,
      nonce,
      deadline,
    },
  );

  const response = await fetch(
    providerUrl(providerEndpointUrl, "/api/v1/auth/requestor-sessions"),
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        requestor_address: requestor,
        vm_id: vmId,
        scope,
        nonce,
        deadline,
        signature,
      }),
    },
  );
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(sessionErrorMessage(response.status, data));
  }
  const session = data as RequestorSessionResponse;
  writeSession(cacheKey, {
    token: session.access_token,
    expiresAt: session.expires_at,
    requestor,
  });
  return session.access_token;
}

async function fetchProviderInfo(
  providerEndpointUrl: string,
): Promise<ProviderInfoResponse> {
  const response = await fetch(
    providerUrl(providerEndpointUrl, "/api/v1/provider/info"),
  );
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(sessionErrorMessage(response.status, data));
  }
  return data as ProviderInfoResponse;
}

function readSession(key: string): CachedSession | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(CACHE_KEY);
    const all = raw ? JSON.parse(raw) : {};
    const value = all[key];
    if (!value || typeof value !== "object") return null;
    return value as CachedSession;
  } catch {
    return null;
  }
}

function writeSession(key: string, session: CachedSession) {
  if (typeof window === "undefined") return;
  const raw = window.sessionStorage.getItem(CACHE_KEY);
  const all = raw ? JSON.parse(raw) : {};
  all[key] = session;
  window.sessionStorage.setItem(CACHE_KEY, JSON.stringify(all));
}

function sessionKey(providerEndpointUrl: string, vmId: string, requestor: string) {
  return `${providerEndpointUrl.replace(/\/$/, "")}:${vmId}:${requestor.toLowerCase()}`;
}

function newNonce() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function sessionErrorMessage(status: number, data: unknown) {
  if (data && typeof data === "object" && "detail" in data) {
    return JSON.stringify((data as { detail: unknown }).detail);
  }
  return `Provider session request failed (${status})`;
}
