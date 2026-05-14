import assert from "node:assert/strict";
import test from "node:test";

import { parseMetricTimestamp } from "../components/vm/details/metrics";

test("rejects timezone-less provider metric timestamps", () => {
  assert.throws(
    () => parseMetricTimestamp("2026-05-12T21:25:44"),
    /explicit timezone/,
  );
});

test("preserves explicit metric timestamp timezone offsets", () => {
  assert.equal(
    parseMetricTimestamp("2026-05-12T23:25:44+02:00"),
    Date.UTC(2026, 4, 12, 21, 25, 44),
  );
});
