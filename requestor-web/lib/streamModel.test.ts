import assert from "node:assert/strict";
import { test } from "node:test";

import {
  remainingTokenBalance,
  spentTokenBalance,
  type StreamRow,
} from "../components/streams/streamModel";

test("stream accounting reports live spent and remaining balances", () => {
  const row = streamRow({
    startTime: 100n,
    stopTime: 200n,
    ratePerSecond: 1_000_000n,
    deposit: 100_000_000n,
  });

  assert.equal(spentTokenBalance(row, 130), 30);
  assert.equal(remainingTokenBalance(row, 130), 70);
});

test("stream accounting stops spending at halted stop time", () => {
  const row = streamRow({
    startTime: 100n,
    stopTime: 150n,
    ratePerSecond: 1_000_000n,
    deposit: 100_000_000n,
    halted: true,
  });

  assert.equal(spentTokenBalance(row, 180), 50);
  assert.equal(remainingTokenBalance(row, 180), 0);
});

function streamRow(chain: Partial<StreamRow["chain"]>): StreamRow {
  return {
    r: {
      name: "vm",
      provider_id: "provider",
      provider_ip: "127.0.0.1",
      vm_id: "vm-id",
      status: "running",
      stream_id: "1",
    },
    chain: {
      token: "0xtoken",
      sender: "0xsender",
      recipient: "0xrecipient",
      startTime: 0n,
      stopTime: 0n,
      ratePerSecond: 0n,
      deposit: 0n,
      withdrawn: 0n,
      halted: false,
      ...chain,
    },
    tokenSymbol: "GLM",
    tokenDecimals: 6,
    usdPrice: 0.2,
  };
}
