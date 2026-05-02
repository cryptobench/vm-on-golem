import assert from "node:assert/strict";
import test from "node:test";

import {
  PAYMENT_PRICE_MAX_AGE_MS,
  ensurePricesUSD,
  getPriceUSD,
  usdToTokenAsync,
} from "./prices";

const KEY_V2 = "requestor_prices_v2";

class MemoryStorage {
  private values = new Map<string, string>();

  getItem(key: string) {
    return this.values.get(key) ?? null;
  }

  setItem(key: string, value: string) {
    this.values.set(key, value);
  }

  removeItem(key: string) {
    this.values.delete(key);
  }

  clear() {
    this.values.clear();
  }
}

const storage = new MemoryStorage();
const listeners = new Map<string, Set<(event: Event) => void>>();

(globalThis as any).localStorage = storage;
(globalThis as any).window = {
  addEventListener(name: string, cb: (event: Event) => void) {
    const handlers = listeners.get(name) || new Set();
    handlers.add(cb);
    listeners.set(name, handlers);
  },
  removeEventListener(name: string, cb: (event: Event) => void) {
    listeners.get(name)?.delete(cb);
  },
  dispatchEvent(event: Event) {
    listeners.get(event.type)?.forEach((cb) => cb(event));
    return true;
  },
};

function reset() {
  storage.clear();
  listeners.clear();
  delete (globalThis as any).fetch;
}

function jsonResponse(body: unknown, init?: ResponseInit) {
  return new Response(JSON.stringify(body), {
    status: 200,
    ...init,
    headers: {
      "content-type": "application/json",
      ...(init?.headers || {}),
    },
  });
}

function binanceBody(eth = "2000", glm = "0.2") {
  return [
    { symbol: "ETHUSDT", price: eth },
    { symbol: "GLMUSDT", price: glm },
  ];
}

function dexBody() {
  return [
    {
      baseToken: { symbol: "WETH" },
      priceUsd: "2100",
      liquidity: { usd: 1000 },
    },
    {
      baseToken: { symbol: "GLM" },
      priceUsd: "0.21",
      liquidity: { usd: 500 },
    },
  ];
}

test("stores Binance prices and broadcasts one update", async () => {
  reset();
  let updates = 0;
  window.addEventListener("requestor_prices_updated", () => {
    updates += 1;
  });
  (globalThis as any).fetch = async (url: string) => {
    assert.match(String(url), /api\.binance\.com/);
    return jsonResponse(binanceBody());
  };

  await ensurePricesUSD({ force: true });

  assert.equal(getPriceUSD("ETH"), 2000);
  assert.equal(getPriceUSD("GLM"), 0.2);
  assert.equal(updates, 1);
});

test("deduplicates concurrent refreshes", async () => {
  reset();
  let calls = 0;
  let releaseFetch: (() => void) | undefined;
  (globalThis as any).fetch = async () => {
    calls += 1;
    await new Promise<void>((resolve) => {
      releaseFetch = resolve;
    });
    return jsonResponse(binanceBody());
  };

  const first = ensurePricesUSD({ force: true });
  const second = ensurePricesUSD({ force: true });
  await new Promise((resolve) => setTimeout(resolve, 0));

  assert.equal(calls, 1);
  assert.ok(releaseFetch);
  releaseFetch();
  await Promise.all([first, second]);
});

test("backs off a rate-limited source and falls through", async () => {
  reset();
  const calls: string[] = [];
  (globalThis as any).fetch = async (url: string) => {
    calls.push(String(url));
    if (String(url).includes("api.binance.com")) {
      return jsonResponse({ error: "rate limited" }, {
        status: 429,
        headers: { "Retry-After": "60" },
      });
    }
    if (String(url).includes("api.dexscreener.com")) {
      return jsonResponse(dexBody());
    }
    throw new Error(`unexpected URL ${url}`);
  };

  await ensurePricesUSD({ force: true });

  assert.match(calls[0], /api\.binance\.com/);
  assert.match(calls[1], /api\.dexscreener\.com/);
  assert.equal(getPriceUSD("ETH"), 2100);
  const stored = JSON.parse(storage.getItem(KEY_V2) || "{}");
  assert.equal(stored.prices.ETH.source, "dexscreener");
  assert.ok(stored.blockedUntil.binance > Date.now());
});

test("payment conversion rejects stale cache when live sources fail", async () => {
  reset();
  const staleAt = Date.now() - PAYMENT_PRICE_MAX_AGE_MS - 1_000;
  storage.setItem(KEY_V2, JSON.stringify({
    prices: {
      ETH: { usd: 2000, source: "binance", updatedAt: staleAt },
      GLM: { usd: 0.2, source: "binance", updatedAt: staleAt },
    },
    blockedUntil: {},
  }));
  (globalThis as any).fetch = async () => jsonResponse({ error: "down" }, { status: 500 });

  await assert.rejects(
    usdToTokenAsync("ETH", 10, { maxAgeMs: PAYMENT_PRICE_MAX_AGE_MS }),
    /returned 500/,
  );
});
