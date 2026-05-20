import type { Rental } from "./api";
import { markRentalTerminated } from "./rentalLifecycle";
import type { VmSafeStatus } from "./requestorVmModel";
import { isTerminatedStream } from "./streams";

type StreamEntryLike =
  | {
      ok: true;
      data: {
        chain: {
          recipient: string;
          stopTime?: bigint | number | string | null;
        };
      };
    }
  | { ok: false; error?: string };

export function reconcileTerminatedStreamRentals(
  rentals: Rental[],
  entries: Record<string, StreamEntryLike | undefined>,
  now = nowSeconds(),
) {
  let changed = false;
  const next = rentals.map((rental) => {
    if (
      isTerminalRental(rental) ||
      rental.stream_id == null ||
      rental.stream_id === ""
    ) {
      return rental;
    }

    const entry = entries[String(rental.stream_id)];
    if (!entry?.ok || !isTerminatedStream(entry.data.chain)) {
      return rental;
    }

    changed = true;
    return markRentalTerminated(rental, {
      at: streamStopTimeSeconds(entry.data.chain.stopTime) || now,
      txHash: rental.settlement_tx_hash ?? null,
      reason: "settled",
      settlementStatus: "settled",
      cleanupState: rental.cleanup_state || "not_started",
      statusMessage: "Lease terminated",
    });
  });

  return { rentals: next, changed };
}

export function reconcileProviderMissingRentals(
  rentals: Rental[],
  statuses: Record<string, VmSafeStatus | null | undefined>,
  now = nowSeconds(),
) {
  let changed = false;
  const next = rentals.map((rental) => {
    if (isTerminalRental(rental)) {
      return rental;
    }

    const status = statuses[rental.vm_id];
    if (!status || status.exists || Number(status.code || 0) !== 404) {
      return rental;
    }

    const createdAt = Number(rental.created_at || 0);
    const currentStatus = String(rental.status || "").toLowerCase();
    const withinCreationGrace =
      currentStatus === "creating" && createdAt > 0 && now - createdAt < 180;
    if (withinCreationGrace) return rental;

    changed = true;
    return {
      ...rental,
      status: "terminated",
      ssh_port: null,
      ended_at: now,
      terminated_at: now,
      termination_reason: "provider_missing",
    };
  });

  return { rentals: next, changed };
}

function isTerminalRental(rental: Rental) {
  const status = String(rental.status || "").toLowerCase();
  return status === "terminated" || status === "deleted";
}

function streamStopTimeSeconds(value?: bigint | number | string | null) {
  if (value == null || value === "") return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) && numeric > 0 ? Math.floor(numeric) : null;
}

function nowSeconds() {
  return Math.floor(Date.now() / 1000);
}
