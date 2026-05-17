import React from "react";
import type { StreamComputed, StreamStatus } from "./types";

const TICK_MS = 1_000;

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
    computed: projectStreamComputed(stream, nowSeconds),
  };
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
  const vestedWei = elapsedSeconds * stream.chain.ratePerSecond;
  const withdrawableWei = Math.max(vestedWei - stream.chain.withdrawn, 0);

  return {
    ...stream.computed,
    now,
    remaining_seconds: Math.max(stopTime - now, 0),
    vested_wei: vestedWei,
    withdrawable_wei: withdrawableWei,
  };
}

function currentUnixSeconds() {
  return Math.floor(Date.now() / 1_000);
}
