import assert from "node:assert/strict";
import test from "node:test";

import {
  endpointHost,
  providerPublicHost,
  sshEndpointLabel,
} from "./providerConnection";

test("builds SSH endpoint from live access host and port", () => {
  assert.equal(
    sshEndpointLabel({
      access: { ssh_host: "203.0.113.10", ssh_port: 50805 },
      provider: { ip_address: "198.51.100.2" },
      rental: {
        provider_endpoint_url: "https://198.51.100.2",
        provider_ip: "192.168.2.13",
        ssh_port: 50804,
      },
    }),
    "203.0.113.10:50805",
  );
});

test("prefers provider public metadata over legacy stored VM IP", () => {
  assert.equal(
    providerPublicHost({
      provider: { ip_address: "198.51.100.2" },
      rental: {
        provider_endpoint_url: "https://198.51.100.2",
        provider_ip: "192.168.2.13",
      },
    }),
    "198.51.100.2",
  );
});

test("does not build SSH endpoint from provider endpoint fallback", () => {
  assert.equal(
    sshEndpointLabel({
      rental: {
        provider_endpoint_url: "https://provider.example:7466",
        provider_ip: "192.168.2.13",
        ssh_port: 50805,
      },
    }),
    "-",
  );
});

test("does not build SSH endpoint from access host without access port", () => {
  assert.equal(
    sshEndpointLabel({
      access: { ssh_host: "203.0.113.10" },
      rental: {
        provider_endpoint_url: "https://198.51.100.2",
        provider_ip: "192.168.2.13",
        ssh_port: 50804,
      },
    }),
    "-",
  );
});

test("extracts provider endpoint host", () => {
  assert.equal(endpointHost("https://203.0.113.10:7466"), "203.0.113.10");
  assert.equal(endpointHost("not a url"), null);
});

test("does not present a host-only value as a connectable SSH endpoint", () => {
  assert.equal(
    sshEndpointLabel({
      provider: { ip_address: "198.51.100.2" },
      rental: {
        provider_endpoint_url: "https://198.51.100.2",
        provider_ip: "192.168.2.13",
      },
    }),
    "-",
  );
});
