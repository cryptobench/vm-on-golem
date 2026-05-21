import assert from "node:assert/strict";
import { test } from "node:test";

import {
  remainingTokenBalance,
  spentTokenBalance,
  streamStatus,
  type StreamRow,
} from "../components/streams/streamModel";

test("stream accounting reports live spent and remaining balances", () => {
  const row = streamRow({
    startTime: 100n,
    stopTime: 200n,
    providerRatePerSecond: 1_000_000n,
    providerDeposit: 100_000_000n,
  });

  assert.equal(spentTokenBalance(row, 130), 30);
  assert.equal(remainingTokenBalance(row, 130), 70);
});

test("stream accounting stops spending at terminated stop time", () => {
  const row = streamRow({
    recipient: "0x0000000000000000000000000000000000000000",
    startTime: 100n,
    stopTime: 150n,
    providerRatePerSecond: 1_000_000n,
    providerDeposit: 100_000_000n,
  });

  assert.equal(spentTokenBalance(row, 180), 50);
  assert.equal(remainingTokenBalance(row, 180), 0);
});

test("stream status keeps expired streams in grace for 30 seconds", () => {
  const row = streamRow({
    startTime: 100n,
    stopTime: 200n,
    providerRatePerSecond: 1_000_000n,
    providerDeposit: 100_000_000n,
  });

  assert.equal(streamStatus(row, 199), "needs-top-up");
  assert.equal(streamStatus(row, 200), "grace");
  assert.equal(streamStatus(row, 229), "grace");
  assert.equal(streamStatus(row, 230), "out-of-funds");
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
      providerRatePerSecond: 0n,
      providerDeposit: 0n,
      providerWithdrawn: 0n,
      donationBps: 0n,
      donationRecipient: "0xdonation",
      donationDeposit: 0n,
      donationWithdrawn: 0n,
      ...chain,
    },
    tokenSymbol: "GLM",
    tokenDecimals: 6,
    usdPrice: 0.2,
  };
}
