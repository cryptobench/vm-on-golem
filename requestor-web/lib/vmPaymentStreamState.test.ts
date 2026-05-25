import assert from "node:assert/strict";
import test from "node:test";

import { isPaymentStreamPanelLoading } from "./vmPaymentStreamState";

test("shows payment stream loading during VM creation when the stream read is not ready", () => {
  assert.equal(
    isPaymentStreamPanelLoading({
      streamId: "42",
      hasStream: false,
      lifecycleStatus: "creating",
      lifecycleStage: "provisioning",
    }),
    true,
  );
});

test("shows payment stream loading for creation stages even when status is unknown", () => {
  assert.equal(
    isPaymentStreamPanelLoading({
      streamId: "42",
      hasStream: false,
      lifecycleStatus: "unknown",
      lifecycleStage: "configuring-access",
    }),
    true,
  );
});

test("does not hide payment stream errors after creation has completed", () => {
  assert.equal(
    isPaymentStreamPanelLoading({
      streamId: "42",
      hasStream: false,
      lifecycleStatus: "running",
      lifecycleStage: "ready",
    }),
    false,
  );
});

test("does not show a loading panel without a mapped stream id", () => {
  assert.equal(
    isPaymentStreamPanelLoading({
      streamId: null,
      hasStream: false,
      lifecycleStatus: "creating",
      lifecycleStage: "provisioning",
    }),
    false,
  );
});
