import assert from "node:assert/strict";
import { test } from "node:test";

import type { Rental } from "./api";
import {
  reconcileProviderMissingRentals,
  reconcileTerminatedStreamRentals,
} from "./rentalReconciliation";

const ZERO_ADDRESS = "0x0000000000000000000000000000000000000000";

const rental: Rental = {
  name: "vm",
  provider_id: "provider",
  provider_endpoint_url: "https://provider.example",
  provider_ip: "127.0.0.1",
  vm_id: "vm-id",
  status: "offline",
  stream_id: "42",
};

test("terminated chain stream marks rental terminated", () => {
  const result = reconcileTerminatedStreamRentals(
    [rental],
    {
      "42": {
        ok: true,
        data: {
          chain: {
            recipient: ZERO_ADDRESS,
            stopTime: 123n,
          },
        },
      },
    },
    456,
  );

  assert.equal(result.changed, true);
  assert.equal(result.rentals[0].status, "terminated");
  assert.equal(result.rentals[0].ended_at, 123);
  assert.equal(result.rentals[0].terminated_at, 123);
  assert.equal(result.rentals[0].settlement_status, "settled");
  assert.equal(result.rentals[0].cleanup_state, "not_started");
  assert.equal(result.rentals[0].status_message, "Lease terminated");
});

test("active chain stream leaves rental unchanged", () => {
  const result = reconcileTerminatedStreamRentals(
    [rental],
    {
      "42": {
        ok: true,
        data: {
          chain: {
            recipient: "0x1111111111111111111111111111111111111111",
            stopTime: 123n,
          },
        },
      },
    },
    456,
  );

  assert.equal(result.changed, false);
  assert.equal(result.rentals[0], rental);
});

test("provider 404 marks non-creating rental terminated", () => {
  const result = reconcileProviderMissingRentals(
    [rental],
    {
      "vm-id": {
        exists: false,
        code: 404,
        error: "not found",
      },
    },
    "default",
    789,
  );

  assert.equal(result.changed, true);
  assert.equal(result.rentals[0].status, "terminated");
  assert.equal(result.rentals[0].terminated_at, 789);
  assert.equal(result.rentals[0].termination_reason, "provider_missing");
});

test("provider 404 keeps fresh creating rental in grace window", () => {
  const result = reconcileProviderMissingRentals(
    [{ ...rental, status: "creating", created_at: 700 }],
    {
      "vm-id": {
        exists: false,
        code: 404,
        error: "not found",
      },
    },
    "default",
    789,
  );

  assert.equal(result.changed, false);
  assert.equal(result.rentals[0].status, "creating");
});
