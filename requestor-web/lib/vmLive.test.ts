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

test("builds provider live websocket URL through the proxy", () => {
  process.env.NEXT_PUBLIC_PORT_CHECKER_URL = "http://localhost:9000";
  process.env.NEXT_PUBLIC_PORT_CHECKER_TOKEN = "secret";

  const url = vmLiveUrl(
    "provider-a",
    "vm-a",
    {
      mode: "central",
      discovery_url: "http://localhost:9001/api/v1",
      arkiv_rpc_url: "http://rpc",
      arkiv_ws_url: "ws://arkiv",
      chain_id: 1,
    },
    { jobId: "job-a", historyRange: "6h" },
  );

  assert.equal(
    url,
    "ws://localhost:9000/proxy/provider/provider-a/api/v1/vms/vm-a/live?port=7466&proxy_source=central&proxy_token=secret&arkiv_rpc_url=http%3A%2F%2Frpc&arkiv_ws_url=ws%3A%2F%2Farkiv&job_id=job-a&history_range=6h",
  );
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
    updated.metricsHistory?.samples.map((sample) => sample.value),
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
