import React from "react";
import type { StreamComputed, StreamStatus } from "./types";

const TICK_MS = 1_000;
const STREAM_GRACE_SECONDS = 30;

export function useStreamNowSeconds() {
  const [nowSeconds, setNowSeconds] = React.useState(() => currentUnixSeconds());

  React.useEffect(() => {
    const timer = window.setInterval(() => {
      setNowSeconds(currentUnixSeconds());
    }, TICK_MS);
    return () => window.clearInterval(timer);
  }, []);

  return nowSeconds;
}

export function projectStreams(streams: StreamStatus[], nowSeconds: number) {
  return streams.map((stream) => projectStream(stream, nowSeconds));
}

export function projectStream(stream: StreamStatus, nowSeconds: number): StreamStatus {
  return {
    ...stream,
    payment_state: projectPaymentState(stream, nowSeconds),
    computed: projectStreamComputed(stream, nowSeconds),
  };
}

function projectPaymentState(stream: StreamStatus, nowSeconds: number) {
  if (stream.payment_state === "terminated" || stream.payment_state === "expired") {
    return stream.payment_state;
  }
  const now = Number.isFinite(nowSeconds)
    ? Math.max(nowSeconds, stream.computed.now)
    : stream.computed.now;
  if (stream.chain.recipient.toLowerCase() === "0x0000000000000000000000000000000000000000") {
    return "terminated";
  }
  if (now >= stream.chain.stopTime + STREAM_GRACE_SECONDS) return "expired";
  if (now >= stream.chain.stopTime) return "grace";
  return stream.payment_state ?? "active";
}

function projectStreamComputed(
  stream: StreamStatus,
  nowSeconds: number,
): StreamComputed {
  const now = Number.isFinite(nowSeconds)
    ? Math.max(nowSeconds, stream.computed.now)
    : stream.computed.now;
  const startTime = stream.chain.startTime;
  const stopTime = stream.chain.stopTime;
  const elapsedSeconds = Math.max(Math.min(now, stopTime) - startTime, 0);
  const providerVestedWei = Math.min(
    elapsedSeconds * stream.chain.providerRatePerSecond,
    stream.chain.providerDeposit,
  );
  const donationVestedWei = Math.min(
    Math.floor((providerVestedWei * stream.chain.donationBps) / 10_000),
    stream.chain.donationDeposit,
  );
  const providerWithdrawableWei = Math.max(
    providerVestedWei - stream.chain.providerWithdrawn,
    0,
  );
  const donationWithdrawableWei = Math.max(
    donationVestedWei - stream.chain.donationWithdrawn,
    0,
  );

  return {
    ...stream.computed,
    now,
    remaining_seconds: Math.max(stopTime - now, 0),
    vested_wei: providerVestedWei + donationVestedWei,
    withdrawable_wei: providerWithdrawableWei + donationWithdrawableWei,
    provider_vested_wei: providerVestedWei,
    provider_withdrawable_wei: providerWithdrawableWei,
    donation_vested_wei: donationVestedWei,
    donation_withdrawable_wei: donationWithdrawableWei,
    total_deposit_wei: stream.chain.providerDeposit + stream.chain.donationDeposit,
  };
}

function currentUnixSeconds() {
  return Math.floor(Date.now() / 1_000);
}
