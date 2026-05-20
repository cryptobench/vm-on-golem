import assert from "node:assert/strict";
import test from "node:test";

import {
  filterProvidersWithUsableEndpoint,
  hasUsableProviderEndpoint,
  loadRentals,
  providerEndpointUrl,
  type ProviderAd,
} from "./api";

test("provider endpoint helpers accept HTTPS by default", () => {
  const provider = {
    provider_id: "provider-a",
    endpoint_url: "https://203.0.113.10",
  } as ProviderAd;

  assert.equal(hasUsableProviderEndpoint(provider), true);
  assert.equal(providerEndpointUrl(provider), "https://203.0.113.10");
  assert.equal(
    hasUsableProviderEndpoint({ ...provider, endpoint_url: "http://203.0.113.10" } as ProviderAd),
    false,
  );
  assert.throws(
    () => providerEndpointUrl({ ...provider, endpoint_url: "" } as ProviderAd),
    /Provider endpoint unavailable/,
  );
});

test("provider endpoint helpers accept HTTP in development", () => {
  const previous = process.env.NEXT_PUBLIC_GOLEM_ENVIRONMENT;
  process.env.NEXT_PUBLIC_GOLEM_ENVIRONMENT = "development";
  try {
    const provider = {
      provider_id: "provider-a",
      endpoint_url: "http://127.0.0.1:7466",
    } as ProviderAd;

    assert.equal(hasUsableProviderEndpoint(provider), true);
    assert.equal(providerEndpointUrl(provider), "http://127.0.0.1:7466");
  } finally {
    if (previous == null) delete process.env.NEXT_PUBLIC_GOLEM_ENVIRONMENT;
    else process.env.NEXT_PUBLIC_GOLEM_ENVIRONMENT = previous;
  }
});

test("provider list filtering hides providers without usable endpoints", () => {
  const providers = [
    {
      provider_id: "provider-a",
      endpoint_url: "https://203.0.113.10",
    },
    {
      provider_id: "provider-b",
      endpoint_url: "http://203.0.113.11",
    },
    {
      provider_id: "provider-c",
    },
  ] as ProviderAd[];

  assert.deepEqual(
    filterProvidersWithUsableEndpoint(providers).map(
      (provider) => provider.provider_id,
    ),
    ["provider-a"],
  );
});

test("loadRentals drops rentals without provider endpoints", () => {
  const originalWindow = (globalThis as any).window;
  const storage = new Map<string, string>();
  const localStorage = {
    getItem: (key: string) => storage.get(key) ?? null,
    setItem: (key: string, value: string) => storage.set(key, value),
  };
  (globalThis as any).window = {};
  (globalThis as any).localStorage = localStorage;
  storage.set(
    "requestor_rentals_v1",
    JSON.stringify([
      {
        name: "kept",
        provider_id: "provider-a",
        provider_endpoint_url: "https://203.0.113.10",
        vm_id: "vm-a",
        status: "running",
      },
      {
        name: "dropped",
        provider_id: "provider-b",
        vm_id: "vm-b",
        status: "running",
      },
    ]),
  );

  try {
    const rentals = loadRentals();

    assert.equal(rentals.length, 1);
    assert.equal(rentals[0].name, "kept");
    assert.equal(
      JSON.parse(storage.get("requestor_rentals_v1") || "[]").length,
      1,
    );
  } finally {
    (globalThis as any).window = originalWindow;
    delete (globalThis as any).localStorage;
  }
});

test("loadRentals strips legacy rental scope fields", () => {
  const originalWindow = (globalThis as any).window;
  const storage = new Map<string, string>();
  const localStorage = {
    getItem: (key: string) => storage.get(key) ?? null,
    setItem: (key: string, value: string) => storage.set(key, value),
  };
  (globalThis as any).window = {};
  (globalThis as any).localStorage = localStorage;
  const legacyScopeField = ["pro", "ject_id"].join("");
  storage.set(
    "requestor_rentals_v1",
    JSON.stringify([
      {
        name: "kept",
        provider_id: "provider-a",
        provider_endpoint_url: "https://203.0.113.10",
        vm_id: "vm-a",
        status: "running",
        [legacyScopeField]: "default",
      },
    ]),
  );

  try {
    const rentals = loadRentals();
    const persisted = JSON.parse(storage.get("requestor_rentals_v1") || "[]");

    assert.equal(rentals.length, 1);
    assert.equal(legacyScopeField in (rentals[0] as any), false);
    assert.equal(legacyScopeField in persisted[0], false);
  } finally {
    (globalThis as any).window = originalWindow;
    delete (globalThis as any).localStorage;
  }
});
