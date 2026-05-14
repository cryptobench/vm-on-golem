import assert from "node:assert/strict";
import { test } from "node:test";
import {
  ensurePaidStreamCanStart,
  terminatePaidRental,
} from "./rentalLifecycle";
import type { Rental } from "./api";

const rental: Rental = {
  name: "vm",
  provider_id: "provider",
  provider_endpoint_url: "https://provider.example",
  provider_ip: "127.0.0.1",
  vm_id: "vm-id",
  status: "running",
  stream_id: "42",
};

test("terminates stream before deleting provider VM and keeps history fields", async () => {
  const calls: string[] = [];

  const next = await terminatePaidRental({
    rental,
    terminateStream: async (streamId) => {
      calls.push(`terminate:${streamId}`);
      return "0xtx";
    },
    destroyVm: async (providerEndpointUrl, vmId) => {
      assert.equal(providerEndpointUrl, "https://provider.example");
      calls.push(`destroy:${vmId}`);
      return null;
    },
    now: () => 123,
  });

  assert.deepEqual(calls, ["terminate:42", "destroy:vm-id"]);
  assert.equal(next.status, "terminated");
  assert.equal(next.terminated_at, 123);
  assert.equal(next.settlement_tx_hash, "0xtx");
  assert.equal(next.settlement_status, "settled");
});

test("failed settlement blocks provider VM deletion", async () => {
  const calls: string[] = [];

  await assert.rejects(
    terminatePaidRental({
      rental,
      terminateStream: async () => {
        calls.push("terminate");
        throw new Error("user rejected");
      },
      destroyVm: async () => {
        calls.push("destroy");
        return null;
      },
    }),
    /user rejected/,
  );

  assert.deepEqual(calls, ["terminate"]);
});

test("provider 404 after settlement is treated as terminated", async () => {
  const next = await terminatePaidRental({
    rental,
    terminateStream: async () => "0xtx",
    destroyVm: async () => {
      throw { status: 404 };
    },
    now: () => 456,
  });

  assert.equal(next.status, "terminated");
  assert.equal(next.terminated_at, 456);
});

test("start guard rejects settled or empty paid streams", async () => {
  await assert.rejects(
    ensurePaidStreamCanStart({
      rental,
      streamPaymentAddress: "0xstream",
      fetchStream: async () => ({
        chain: {
          token: "0xtoken",
          sender: "0xsender",
          recipient: "0x0000000000000000000000000000000000000000",
          startTime: 1n,
          stopTime: 100n,
          ratePerSecond: 1n,
          deposit: 100n,
          withdrawn: 0n,
          halted: false,
        },
        remaining: 10n,
        tokenSymbol: "GLM",
        tokenDecimals: 18,
        usdPrice: null,
      }),
    }),
    /already settled/,
  );
});
