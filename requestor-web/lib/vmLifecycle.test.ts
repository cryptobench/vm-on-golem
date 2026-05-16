import assert from "node:assert/strict";
import { test } from "node:test";
import { deriveVmDisplayLifecycle, deriveVmLifecycle } from "./vmLifecycle";

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

test("represents provider unreachable as offline", () => {
  const lifecycle = deriveVmLifecycle({ status: "offline" });

  assert.equal(lifecycle.status, "offline");
  assert.equal(lifecycle.label, "Offline");
  assert.equal(lifecycle.message, "Provider unreachable");
  assert.equal(lifecycle.tone, "danger");
  assert.equal(lifecycle.transitioning, false);
  assert.equal(lifecycle.progress, 0);
});

test("display lifecycle uses reachable provider status", () => {
  const lifecycle = deriveVmDisplayLifecycle({
    lifecycle: { status: "running" },
    fallback: { status: "stopped" },
    safeStatus: { exists: true, data: { status: "running" } },
  });

  assert.equal(lifecycle.status, "running");
  assert.equal(lifecycle.label, "Online");
});

test("display lifecycle maps non-404 safe status failures to offline", () => {
  const lifecycle = deriveVmDisplayLifecycle({
    lifecycle: { status: "running" },
    fallback: { status: "running" },
    safeStatus: { exists: false, code: 502, error: "Upstream error" },
  });

  assert.equal(lifecycle.status, "offline");
  assert.equal(lifecycle.label, "Offline");
  assert.equal(lifecycle.message, "Provider unreachable");
  assert.equal(lifecycle.stage, "running");
});

test("display lifecycle keeps creating badge when provider is unreachable during creation", () => {
  const lifecycle = deriveVmDisplayLifecycle({
    lifecycle: { status: "offline", lifecycle_stage: "launching" },
    fallback: { status: "creating", lifecycle_stage: "launching" },
    safeStatus: { exists: false, code: 502, error: "Upstream error" },
  });

  assert.equal(lifecycle.status, "creating");
  assert.equal(lifecycle.label, "Creating");
  assert.equal(lifecycle.message, "Provider unreachable");
  assert.equal(lifecycle.transitioning, true);
  assert.equal(lifecycle.tone, "primary");
});

test("display lifecycle keeps failed job status when VM endpoints are unreachable", () => {
  const lifecycle = deriveVmDisplayLifecycle({
    lifecycle: {
      status: "failed",
      lifecycle_stage: "failed",
      status_message: "VM creation failed",
      progress: 100,
    },
    safeStatus: { exists: false, code: 403, error: "VM owner unavailable" },
  });

  assert.equal(lifecycle.status, "failed");
  assert.equal(lifecycle.label, "Failed");
  assert.equal(lifecycle.message, "VM creation failed");
  assert.equal(lifecycle.transitioning, false);
  assert.equal(lifecycle.tone, "danger");
});

test("display lifecycle does not classify 404 as offline", () => {
  const lifecycle = deriveVmDisplayLifecycle({
    fallback: { status: "running" },
    safeStatus: { exists: false, code: 404, error: "not found" },
  });

  assert.equal(lifecycle.status, "running");
});

test("display lifecycle keeps local transitional state for unknown provider status", () => {
  const lifecycle = deriveVmDisplayLifecycle({
    lifecycle: { status: "unknown" },
    fallback: { status: "creating", lifecycle_stage: "provisioning" },
  });

  assert.equal(lifecycle.status, "creating");
  assert.equal(lifecycle.transitioning, true);
});

test("display lifecycle recovers from offline when safe status succeeds", () => {
  const lifecycle = deriveVmDisplayLifecycle({
    lifecycle: { status: "running" },
    fallback: { status: "offline" },
    safeStatus: { exists: true, data: { status: "running" } },
  });

  assert.equal(lifecycle.status, "running");
  assert.equal(lifecycle.label, "Online");
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
    "offline",
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
