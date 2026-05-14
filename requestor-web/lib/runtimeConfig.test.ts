import assert from "node:assert/strict";
import test from "node:test";

import {
  getRequestorRuntimeConfig,
  setRequestorRuntimeConfig,
} from "./runtimeConfig";

test("runtime config falls back to public env values", () => {
  process.env.NEXT_PUBLIC_DISCOVERY_API_URL = "http://127.0.0.1:9001/api/v1";
  process.env.NEXT_PUBLIC_STREAM_PAYMENT_ADDRESS = "0x123";

  const config = getRequestorRuntimeConfig();

  assert.equal(config.discoveryApiUrl, "http://127.0.0.1:9001/api/v1");
  assert.equal(config.streamPaymentAddress, "0x123");
});

test("runtime config keeps built-in defaults when env values are unset", () => {
  delete process.env.NEXT_PUBLIC_DISCOVERY_API_URL;
  delete process.env.NEXT_PUBLIC_EVM_CHAIN_ID;

  const config = getRequestorRuntimeConfig();

  assert.equal(config.discoveryApiUrl, "http://195.201.39.101:9001/api/v1");
  assert.equal(config.evmChainId, "0x88bb0");
});

test("runtime config prefers desktop overrides", () => {
  const originalWindow = (globalThis as any).window;
  (globalThis as any).window = {};
  try {
    process.env.NEXT_PUBLIC_DISCOVERY_API_URL = "http://127.0.0.1:9100/api/v1";
    setRequestorRuntimeConfig({
      discoveryApiUrl: "http://127.0.0.1:9200/api/v1",
      golemEnvironment: "development",
    });

    const config = getRequestorRuntimeConfig();

    assert.equal(config.discoveryApiUrl, "http://127.0.0.1:9200/api/v1");
    assert.equal(config.golemEnvironment, "development");
  } finally {
    (globalThis as any).window = originalWindow;
  }
});
