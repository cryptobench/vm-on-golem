import assert from "node:assert/strict";
import test from "node:test";

import {
  applyDiscoveryEvent,
  countriesFromProviders,
  DISCOVERY_RECONNECT_INITIAL_DELAY_MS,
  DISCOVERY_RECONNECT_MAX_DELAY_MS,
  nextDiscoveryReconnectDelayMs,
  subscribeMessage,
} from "./discovery";
import type { ProviderAd } from "./api";

test("subscribe message strips empty filters", () => {
  assert.deepEqual(
    subscribeMessage({ cpu: 2, country: "", platform: "arm64" }),
    {
      type: "subscribe",
      filters: { cpu: 2, platform: "arm64" },
    },
  );
});

test("discovery events apply snapshot upsert and remove", () => {
  const first = provider("p1", 2);
  const second = provider("p2", 4);

  let rows = applyDiscoveryEvent([], {
    type: "snapshot",
    advertisements: [first],
  });
  assert.deepEqual(rows.map((row) => row.provider_id), ["p1"]);

  rows = applyDiscoveryEvent(rows, {
    type: "provider.upsert",
    advertisement: second,
  });
  assert.deepEqual(
    rows.map((row) => row.provider_id).sort(),
    ["p1", "p2"],
  );

  rows = applyDiscoveryEvent(rows, {
    type: "provider.remove",
    provider_id: "p1",
  });
  assert.deepEqual(rows.map((row) => row.provider_id), ["p2"]);
});

test("countries derive from current connected providers", () => {
  assert.deepEqual(
    countriesFromProviders([provider("p1", 2, "se"), provider("p2", 2, "US")]),
    ["SE", "US"],
  );
});

test("discovery reconnect delay backs off and caps", () => {
  let delay = DISCOVERY_RECONNECT_INITIAL_DELAY_MS;

  delay = nextDiscoveryReconnectDelayMs(delay);
  assert.equal(delay, 2000);

  delay = nextDiscoveryReconnectDelayMs(delay);
  assert.equal(delay, 4000);

  delay = nextDiscoveryReconnectDelayMs(DISCOVERY_RECONNECT_MAX_DELAY_MS);
  assert.equal(delay, DISCOVERY_RECONNECT_MAX_DELAY_MS);
});

function provider(id: string, cpu: number, country = "US"): ProviderAd {
  return {
    provider_id: id,
    ip_address: "1.2.3.4",
    country,
    platform: "arm64",
    endpoint_url: "https://provider.example",
    resources: { cpu, memory: 4, storage: 10 },
    pricing: null,
    created_at: "2026-05-17T12:00:00+00:00",
    updated_at: "2026-05-17T12:00:00+00:00",
  };
}
