import assert from "node:assert/strict";
import { test } from "node:test";
import { deriveVmLifecycle } from "./vmLifecycle";

test("keeps local transitional state when provider is temporarily unknown", () => {
  const lifecycle = deriveVmLifecycle(
    { status: "unknown" },
    { status: "creating", lifecycle_stage: "provisioning" },
  );

  assert.equal(lifecycle.status, "creating");
  assert.equal(lifecycle.transitioning, true);
  assert.equal(lifecycle.label, "Creating");
});

test("uses provider progress and message for creation jobs", () => {
  const lifecycle = deriveVmLifecycle({
    status: "creating",
    lifecycle_stage: "configuring_access",
    status_message: "Configuring SSH access",
    progress: 90,
    next_poll_seconds: 2,
  });

  assert.equal(lifecycle.stage, "configuring_access");
  assert.equal(lifecycle.message, "Configuring SSH access");
  assert.equal(lifecycle.progress, 90);
  assert.equal(lifecycle.nextPollMs, 2000);
});

test("represents every provider VM status", () => {
  for (const status of [
    "creating",
    "starting",
    "restarting",
    "running",
    "delayed_shutdown",
    "suspending",
    "suspended",
    "stopping",
    "stopped",
    "error",
    "deleted",
    "unknown",
  ]) {
    const lifecycle = deriveVmLifecycle({ status });

    assert.equal(lifecycle.status, status);
    assert.ok(lifecycle.label.length > 0);
    assert.ok(lifecycle.message.length > 0);
    assert.ok(lifecycle.progress >= 0);
    assert.ok(lifecycle.progress <= 100);
  }
});
