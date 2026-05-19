import assert from "node:assert/strict";
import test from "node:test";

import {
  getRequestorRuntimeConfig,
  setRequestorRuntimeConfig,
} from "./runtimeConfig";

test("runtime config falls back to public env values", () => {
  process.env.NEXT_PUBLIC_DISCOVERY_WS_URL =
    "ws://127.0.0.1:9001/api/v1/discovery/requestors";
  process.env.NEXT_PUBLIC_STREAM_PAYMENT_ADDRESS = "0x123";

  const config = getRequestorRuntimeConfig();

  assert.equal(
    config.discoveryWsUrl,
    "ws://127.0.0.1:9001/api/v1/discovery/requestors",
  );
  assert.equal(config.streamPaymentAddress, "0x123");
});

test("runtime config keeps built-in defaults when env values are unset", () => {
  delete process.env.NEXT_PUBLIC_DISCOVERY_WS_URL;
  delete process.env.NEXT_PUBLIC_EVM_CHAIN_ID;

  const config = getRequestorRuntimeConfig();

  assert.equal(
    config.discoveryWsUrl,
    "wss://78.46.172.104/api/v1/discovery/requestors",
  );
  assert.equal(config.evmChainId, "0x88bb0");
});

test("runtime config prefers window runtime overrides", () => {
  const originalWindow = (globalThis as any).window;
  (globalThis as any).window = {};
  try {
    process.env.NEXT_PUBLIC_DISCOVERY_WS_URL =
      "ws://127.0.0.1:9100/api/v1/discovery/requestors";
    setRequestorRuntimeConfig({
      discoveryWsUrl: "ws://127.0.0.1:9200/api/v1/discovery/requestors",
      golemEnvironment: "development",
    });

    const config = getRequestorRuntimeConfig();

    assert.equal(
      config.discoveryWsUrl,
      "ws://127.0.0.1:9200/api/v1/discovery/requestors",
    );
    assert.equal(config.golemEnvironment, "development");
  } finally {
    (globalThis as any).window = originalWindow;
  }
});
