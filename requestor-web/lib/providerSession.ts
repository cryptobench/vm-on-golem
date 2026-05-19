"use client";

import { BrowserProvider } from "ethers";
import { getInjectedEthereum } from "./walletClient";
import { normalizeProviderEndpoint, providerUrl } from "./providerEndpoint";

type ProviderInfoResponse = {
  provider_id: string;
};

type RequestorSessionResponse = {
  access_token: string;
  expires_at: number;
  requestor_address: string;
  vm_id?: string | null;
  scope?: string;
};

const CACHE_KEY = "golem_provider_vm_sessions_v1";
const EXPIRY_SKEW_SECONDS = 30;
const PROVIDER_SESSION_TTL_SECONDS = 86400;

type CachedSession = {
  token: string;
  expiresAt: number;
  requestor: string;
  providerId: string;
};

type ProviderSessionSigner = {
  getAddress: () => Promise<string>;
  signTypedData: (
    domain: Record<string, unknown>,
    types: Record<string, Array<{ name: string; type: string }>>,
    value: Record<string, unknown>,
  ) => Promise<string>;
};

type ProviderSessionDeps = {
  getSigner: () => Promise<ProviderSessionSigner>;
  fetch: typeof fetch;
  now: () => number;
  nonce: () => string;
};

type ProviderSessionOptions = {
  interactive?: boolean;
};

const pendingSessions = new Map<string, Promise<string>>();
const blockedSessionKeys = new Set<string>();

let deps: ProviderSessionDeps = {
  getSigner: getProviderSessionSigner,
  fetch: (...args) => fetch(...args),
  now: () => Date.now(),
  nonce: newNonce,
};

export class ProviderSessionAuthError extends Error {
  code: "auth_required" | "auth_rejected";

  constructor(code: "auth_required" | "auth_rejected", message: string) {
    super(message);
    this.name = "ProviderSessionAuthError";
    this.code = code;
  }
}

export async function getProviderVmSession(
  providerEndpointUrl: string,
  _vmId: string,
  options: ProviderSessionOptions = {},
): Promise<string> {
  const endpoint = normalizeProviderEndpoint(providerEndpointUrl);
  const pending = pendingSessions.get(endpoint);
  if (pending) return pending;
  if (!options.interactive && blockedSessionKeys.has(endpoint)) {
    throw new ProviderSessionAuthError(
      "auth_required",
      "Provider session authorization required.",
    );
  }

  const promise = createProviderSession(endpoint, options).finally(() => {
    pendingSessions.delete(endpoint);
  });
  pendingSessions.set(endpoint, promise);
  return promise;
}

export function resetProviderSessionAuthBlock(providerEndpointUrl?: string) {
  if (!providerEndpointUrl) {
    blockedSessionKeys.clear();
    return;
  }
  blockedSessionKeys.delete(normalizeProviderEndpoint(providerEndpointUrl));
}

async function createProviderSession(
  providerEndpointUrl: string,
  options: ProviderSessionOptions,
): Promise<string> {
  try {
    const [provider, signer] = await Promise.all([
      fetchProviderInfo(providerEndpointUrl),
      deps.getSigner(),
    ]);
    const requestor = await signer.getAddress();
    const cacheKey = sessionKey(providerEndpointUrl, provider.provider_id, requestor);
    const cached = readSession(cacheKey);
    const now = Math.floor(deps.now() / 1000);
    if (cached && cached.expiresAt - EXPIRY_SKEW_SECONDS > now) {
      return cached.token;
    }
    if (!options.interactive && blockedSessionKeys.has(providerEndpointUrl)) {
      throw new ProviderSessionAuthError(
        "auth_required",
        "Provider session authorization required.",
      );
    }

    const deadline = now + PROVIDER_SESSION_TTL_SECONDS;
    const nonce = deps.nonce();
    const scope = "provider";
    const signature = await signer.signTypedData(
      { name: "GolemProviderSession", version: "1" },
      {
        ProviderSession: [
          { name: "provider", type: "address" },
          { name: "requestor", type: "address" },
          { name: "scope", type: "string" },
          { name: "nonce", type: "string" },
          { name: "deadline", type: "uint256" },
        ],
      },
      {
        provider: provider.provider_id,
        requestor,
        scope,
        nonce,
        deadline,
      },
    );

    const response = await deps.fetch(
      providerUrl(providerEndpointUrl, "/api/v1/auth/requestor-sessions"),
      {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          requestor_address: requestor,
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
      providerId: provider.provider_id,
    });
    blockedSessionKeys.delete(providerEndpointUrl);
    return session.access_token;
  } catch (error) {
    if (isWalletRejection(error)) {
      blockedSessionKeys.add(providerEndpointUrl);
      throw new ProviderSessionAuthError(
        "auth_rejected",
        "Provider session authorization was rejected.",
      );
    }
    throw error;
  }
}

async function fetchProviderInfo(
  providerEndpointUrl: string,
): Promise<ProviderInfoResponse> {
  const response = await deps.fetch(
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

function sessionKey(
  providerEndpointUrl: string,
  providerId: string,
  requestor: string,
) {
  return [
    providerEndpointUrl,
    providerId.toLowerCase(),
    requestor.toLowerCase(),
  ].join(":");
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

function isWalletRejection(error: unknown) {
  const maybe = error as { code?: unknown; message?: unknown };
  const code = Number(maybe?.code);
  const message = String(maybe?.message || "").toLowerCase();
  return (
    code === 4001 ||
    code === -32002 ||
    message.includes("rejected") ||
    message.includes("denied") ||
    message.includes("already pending")
  );
}

export function __setProviderSessionTestDeps(
  next: Partial<ProviderSessionDeps> | null,
) {
  if (next == null) {
    deps = {
      getSigner: getProviderSessionSigner,
      fetch: (...args) => fetch(...args),
      now: () => Date.now(),
      nonce: newNonce,
    };
    pendingSessions.clear();
    blockedSessionKeys.clear();
    return;
  }
  deps = { ...deps, ...next };
  pendingSessions.clear();
  blockedSessionKeys.clear();
}

async function getProviderSessionSigner(): Promise<ProviderSessionSigner> {
  const ethereum = getInjectedEthereum();
  if (!ethereum?.request) {
    throw new ProviderSessionAuthError(
      "auth_required",
      "Wallet connection required for provider session authorization.",
    );
  }
  const provider = new BrowserProvider(ethereum);
  return provider.getSigner();
}
