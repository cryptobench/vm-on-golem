import assert from "node:assert/strict";
import test from "node:test";

import { vmLiveUrl } from "./api";
import { vmLiveReducer, type VmLiveState } from "../hooks/useVmLive";

const baseState: VmLiveState = {
  connection: "idle",
  providerInfo: null,
  lifecycle: null,
  access: null,
  job: null,
  snapshots: null,
  stream: null,
  metricsLatest: null,
  metricsHistory: null,
  errors: {},
};

test("builds provider live websocket URL from HTTPS endpoint", () => {
  const url = vmLiveUrl(
    "https://203.0.113.10",
    "vm-a",
    { jobId: "job-a", historyRange: "6h" },
  );

  assert.equal(
    url,
    "wss://203.0.113.10/api/v1/vms/vm-a/live?job_id=job-a&history_range=6h",
  );
});

test("builds provider live websocket URL from HTTP development endpoint", () => {
  const previous = process.env.NEXT_PUBLIC_GOLEM_ENVIRONMENT;
  process.env.NEXT_PUBLIC_GOLEM_ENVIRONMENT = "development";
  try {
    const url = vmLiveUrl("http://127.0.0.1:7466", "vm-a", {});

    assert.equal(url, "ws://127.0.0.1:7466/api/v1/vms/vm-a/live");
  } finally {
    if (previous == null) delete process.env.NEXT_PUBLIC_GOLEM_ENVIRONMENT;
    else process.env.NEXT_PUBLIC_GOLEM_ENVIRONMENT = previous;
  }
});

test("live reducer applies snapshots and metric updates", () => {
  const snapshot = vmLiveReducer(baseState, {
    type: "snapshot",
    data: {
      lifecycle: { status: "running" },
      snapshots: [{ name: "snap-a" }],
      metrics_latest: { host: {}, vms: {}, generated_at: "now" },
      metrics_history: { samples: [] },
    },
  });
  const updated = vmLiveReducer(snapshot, {
    type: "update",
    scope: "metrics",
    data: {
      latest: {
        host: {},
        vms: {
          "vm-a": {
            guest_agent: {
              cpu_percent: {
                value: 12,
                unit: "percent",
                timestamp: "now",
                source: "guest_agent",
              },
            },
          },
        },
        generated_at: "later",
      },
      history: { samples: [] },
    },
  });

  assert.equal(updated.lifecycle?.status, "running");
  assert.equal(updated.snapshots?.[0].name, "snap-a");
  assert.equal(
    updated.metricsLatest?.vms["vm-a"].guest_agent.cpu_percent.value,
    12,
  );
});

test("live reducer appends metric samples from streaming updates", () => {
  const snapshot = vmLiveReducer(baseState, {
    type: "snapshot",
    data: {
      metrics_history: {
        samples: [metricSample("cpu_percent", 12, "2026-05-12T21:00:00")],
      },
    },
  });
  const updated = vmLiveReducer(snapshot, {
    type: "update",
    scope: "metrics",
    data: {
      samples: [
        metricSample("cpu_percent", 14, "2026-05-12T21:00:01"),
        metricSample("cpu_percent", 14, "2026-05-12T21:00:01"),
      ],
    },
  });

  assert.deepEqual(
    updated.metricsHistory?.samples?.map((sample) => sample.value),
    [12, 14],
  );
});

test("live reducer keeps live metric samples when history refreshes", () => {
  const withLiveSamples = vmLiveReducer(baseState, {
    type: "snapshot",
    data: {
      metrics_history: {
        points: [metricPoint("cpu_percent", 10, "2026-05-12T21:00:00")],
        samples: [
          metricSample("cpu_percent", 12, "2026-05-12T21:00:01"),
          metricSample("cpu_percent", 14, "2026-05-12T21:00:02"),
        ],
      },
    },
  });

  const refreshed = vmLiveReducer(withLiveSamples, {
    type: "update",
    scope: "metrics",
    data: {
      history: {
        points: [metricPoint("cpu_percent", 16, "2026-05-12T21:00:10")],
      },
    },
  });

  assert.deepEqual(
    refreshed.metricsHistory?.points?.map((point) => point.avg),
    [16],
  );
  assert.deepEqual(
    refreshed.metricsHistory?.samples?.map((sample) => sample.value),
    [12, 14],
  );
});

test("live reducer records degraded connection state", () => {
  const updated = vmLiveReducer(baseState, {
    type: "degraded",
    error: "Live stream unavailable",
  });

  assert.equal(updated.connection, "degraded");
  assert.equal(updated.errors.connection, "Live stream unavailable");
});

function metricSample(metric: string, value: number, timestamp: string) {
  return {
    scope: "vm",
    source: "guest_agent",
    metric,
    value,
    unit: "percent",
    timestamp,
    vm_id: "vm-a",
  } as const;
}

function metricPoint(metric: string, avg: number, bucketEnd: string) {
  return {
    scope: "vm",
    source: "guest_agent",
    metric,
    avg,
    min: avg,
    max: avg,
    count: 1,
    unit: "percent",
    bucket_start: bucketEnd,
    bucket_end: bucketEnd,
    vm_id: "vm-a",
  } as const;
}
