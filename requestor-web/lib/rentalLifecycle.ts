import type { AdsConfig, Rental } from "./api";
import { vmDestroy } from "./api";
import { fetchStreamWithMeta } from "./streams";

const ZERO_ADDRESS = "0x0000000000000000000000000000000000000000";

export type TerminateRentalOptions = {
  rental: Rental;
  ads: AdsConfig;
  terminateStream: (streamId: string | number | bigint) => Promise<string>;
  destroyVm?: typeof vmDestroy;
  now?: () => number;
};

export type StartGuardOptions = {
  rental: Rental;
  streamPaymentAddress: string;
  fetchStream?: typeof fetchStreamWithMeta;
  now?: () => number;
};

export async function terminatePaidRental({
  rental,
  ads,
  terminateStream,
  destroyVm = vmDestroy,
  now = nowSeconds,
}: TerminateRentalOptions): Promise<Rental> {
  let txHash: string | null = null;
  const streamId = rental.stream_id;

  if (streamId != null && streamId !== "") {
    try {
      txHash = await terminateStream(streamId);
    } catch (error) {
      if (!looksLikeNoStream(error)) throw error;
    }
  }

  try {
    await destroyVm(rental.provider_id, rental.vm_id, ads);
  } catch (error) {
    if (!isNotFoundError(error)) throw error;
  }

  return markRentalTerminated(rental, {
    at: now(),
    txHash,
    reason: streamId == null || streamId === "" ? "provider_deleted" : "settled",
    settlementStatus: streamId == null || streamId === "" ? "not_required" : "settled",
  });
}

export async function ensurePaidStreamCanStart({
  rental,
  streamPaymentAddress,
  fetchStream = fetchStreamWithMeta,
  now = nowSeconds,
}: StartGuardOptions): Promise<void> {
  if (rental.stream_id == null || rental.stream_id === "") return;
  if (!streamPaymentAddress) {
    throw new Error("StreamPayment address missing. Configure Settings before starting this paid VM.");
  }

  const stream = await fetchStream(streamPaymentAddress, BigInt(rental.stream_id));
  if (stream.chain.recipient.toLowerCase() === ZERO_ADDRESS) {
    throw new Error("Payment stream is already settled. Terminate this VM or create a new rental.");
  }
  if (stream.chain.halted) {
    throw new Error("Payment stream is halted. Terminate this VM or create a new rental.");
  }
  const remaining = Number(stream.remaining);
  if (!Number.isFinite(remaining) || remaining <= 0 || Number(stream.chain.stopTime) <= now()) {
    throw new Error("Payment stream has no remaining runway. Top up before starting this VM.");
  }
}

export function markRentalTerminated(
  rental: Rental,
  {
    at = nowSeconds(),
    txHash = null,
    reason = "settled",
    settlementStatus = "settled",
  }: {
    at?: number;
    txHash?: string | null;
    reason?: string;
    settlementStatus?: Rental["settlement_status"];
  } = {},
): Rental {
  return {
    ...rental,
    status: "terminated",
    ssh_port: null,
    ended_at: at,
    terminated_at: at,
    end_reason: reason,
    termination_reason: reason,
    settlement_tx_hash: txHash,
    settlement_status: settlementStatus,
  };
}

export function markCreateFailedSettled(
  rental: Rental,
  {
    at = nowSeconds(),
    txHash,
  }: {
    at?: number;
    txHash: string;
  },
): Rental {
  return {
    ...markRentalTerminated(rental, {
      at,
      txHash,
      reason: "create_failed",
      settlementStatus: "settled",
    }),
    create_failed_at: at,
    status_message: "VM creation failed; stream settled",
  };
}

function isNotFoundError(error: unknown) {
  return (error as { status?: number } | null)?.status === 404;
}

function looksLikeNoStream(error: unknown) {
  const text =
    error instanceof Error ? error.message : JSON.stringify(error ?? "");
  return text.toLowerCase().includes("no-stream");
}

function nowSeconds() {
  return Math.floor(Date.now() / 1000);
}
