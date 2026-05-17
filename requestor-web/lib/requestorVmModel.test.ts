import assert from "node:assert/strict";
import { test } from "node:test";

import type { Rental } from "./api";
import { buildRequestorVmModel } from "./requestorVmModel";

const rental: Rental = {
  name: "vm",
  provider_id: "provider",
  provider_endpoint_url: "https://provider.example",
  provider_ip: "127.0.0.1",
  vm_id: "vm-id",
  status: "running",
  stream_id: "42",
  resources: { cpu: 1, memory: 2, storage: 19 },
};

test("requestor VM model maps provider status failures to offline", () => {
  const model = buildRequestorVmModel(rental, {
    provider: null,
    providerError: new Error("provider unavailable"),
    safeStatus: {
      exists: false,
      code: 0,
      error: "provider unavailable",
    },
    access: null,
    accessError: new Error("provider unavailable"),
    stream: null,
    streamError: null,
  });

  assert.equal(model.lifecycle.status, "offline");
  assert.equal(model.lifecycle.label, "Offline");
  assert.equal(model.resources?.cpu, 1);
});

test("requestor VM model uses reachable provider status and access", () => {
  const model = buildRequestorVmModel(rental, {
    provider: {
      country: "SE",
      platform: "arm64",
      ip_address: "192.168.50.48",
    },
    providerError: null,
    safeStatus: {
      exists: true,
      data: {
        status: "running",
        resources: { cpu: 2, memory: 4, storage: 40 },
      },
    },
    access: {
      ssh_host: "192.168.50.48",
      ssh_port: 50805,
    },
    accessError: null,
    stream: {
      computed: { remaining_seconds: 60 },
    },
    streamError: null,
  });

  assert.equal(model.lifecycle.status, "running");
  assert.equal(model.country, "SE");
  assert.equal(model.platform, "arm64");
  assert.equal(model.resources?.cpu, 2);
  assert.equal(model.sshEndpoint, "192.168.50.48:50805");
  assert.equal(model.remainingSeconds, 60);
});
