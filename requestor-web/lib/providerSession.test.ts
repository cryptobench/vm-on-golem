import assert from "node:assert/strict";
import test from "node:test";

import {
  __setProviderSessionTestDeps,
  getProviderVmSession,
  ProviderSessionAuthError,
  resetProviderSessionAuthBlock,
} from "./providerSession";

const REQUESTOR = "0x3333333333333333333333333333333333333333";
const PROVIDER_A = "0x2222222222222222222222222222222222222222";
const PROVIDER_B = "0x4444444444444444444444444444444444444444";

test("dedupes concurrent provider session signatures across VMs", async () => {
  const calls = testContext();

  const [first, second, third] = await Promise.all([
    getProviderVmSession("https://provider.example", "vm-a"),
    getProviderVmSession("https://provider.example", "vm-b"),
    getProviderVmSession("https://provider.example", "vm-a"),
  ]);

  assert.equal(first, "token-1");
  assert.equal(second, "token-1");
  assert.equal(third, "token-1");
  assert.equal(calls.signatures, 1);
  assert.equal(calls.sessions, 1);
  teardown();
});

test("reuses provider-scoped cache for later VM requests", async () => {
  const calls = testContext();

  const first = await getProviderVmSession("https://provider.example", "vm-a");
  const second = await getProviderVmSession("https://provider.example", "vm-b");

  assert.equal(first, "token-1");
  assert.equal(second, "token-1");
  assert.equal(calls.signatures, 1);
  assert.equal(calls.sessions, 1);
  teardown();
});

test("keeps provider sessions isolated by provider", async () => {
  const calls = testContext({
    providerIdForUrl: (url) =>
      url.includes("provider-b.example") ? PROVIDER_B : PROVIDER_A,
  });

  await getProviderVmSession("https://provider-a.example", "vm-a");
  await getProviderVmSession("https://provider-b.example", "vm-a");

  assert.equal(calls.signatures, 2);
  assert.equal(calls.sessions, 2);
  teardown();
});

test("suppresses background signature retries after rejection", async () => {
  const calls = testContext({ rejectSignature: true });

  await assert.rejects(
    getProviderVmSession("https://provider.example", "vm-a"),
    (error) =>
      error instanceof ProviderSessionAuthError &&
      error.code === "auth_rejected",
  );
  await assert.rejects(
    getProviderVmSession("https://provider.example", "vm-b"),
    (error) =>
      error instanceof ProviderSessionAuthError &&
      error.code === "auth_required",
  );

  assert.equal(calls.signatures, 1);
  teardown();
});

test("allows an explicit retry after background auth was blocked", async () => {
  const calls = testContext({ rejectSignature: true });

  await assert.rejects(getProviderVmSession("https://provider.example", "vm-a"));
  calls.rejectSignature = false;
  __setProviderSessionTestDeps({
    getSigner: async () => signer(calls),
    fetch: fakeFetch(calls),
    now: () => 1_000_000,
    nonce: () => `nonce-${calls.signatures + 1}`,
  });
  resetProviderSessionAuthBlock("https://provider.example");

  const token = await getProviderVmSession("https://provider.example", "vm-b", {
    interactive: true,
  });

  assert.equal(token, "token-1");
  assert.equal(calls.signatures, 2);
  teardown();
});

function testContext(
  options: {
    rejectSignature?: boolean;
    providerIdForUrl?: (url: string) => string;
  } = {},
) {
  const storage = new Map<string, string>();
  const calls = {
    signatures: 0,
    sessions: 0,
    rejectSignature: Boolean(options.rejectSignature),
    providerIdForUrl: options.providerIdForUrl || (() => PROVIDER_A),
  };
  (globalThis as any).window = {
    sessionStorage: {
      getItem: (key: string) => storage.get(key) ?? null,
      setItem: (key: string, value: string) => storage.set(key, value),
      removeItem: (key: string) => storage.delete(key),
      clear: () => storage.clear(),
    },
  };
  __setProviderSessionTestDeps({
    getSigner: async () => signer(calls),
    fetch: fakeFetch(calls),
    now: () => 1_000_000,
    nonce: () => `nonce-${calls.signatures + 1}`,
  });
  return calls;
}

function teardown() {
  __setProviderSessionTestDeps(null);
  delete (globalThis as any).window;
}

function signer(calls: { signatures: number; rejectSignature: boolean }) {
  return {
    getAddress: async () => REQUESTOR,
    signTypedData: async () => {
      calls.signatures += 1;
      if (calls.rejectSignature) {
        const error = new Error("User rejected the request") as Error & {
          code: number;
        };
        error.code = 4001;
        throw error;
      }
      return `0xsignature-${calls.signatures}`;
    },
  };
}

function fakeFetch(calls: {
  sessions: number;
  providerIdForUrl: (url: string) => string;
}) {
  return async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.endsWith("/api/v1/provider/info")) {
      return jsonResponse({ provider_id: calls.providerIdForUrl(url) });
    }
    if (url.endsWith("/api/v1/auth/requestor-sessions")) {
      calls.sessions += 1;
      return jsonResponse({
        access_token: `token-${calls.sessions}`,
        expires_at: 1_000_000 + 86_400,
        requestor_address: REQUESTOR,
        scope: "provider",
      });
    }
    return jsonResponse({ detail: "not found" }, 404);
  };
}

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}
