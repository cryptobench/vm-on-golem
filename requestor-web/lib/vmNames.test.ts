import assert from "node:assert/strict";
import test from "node:test";

import { generateVmName } from "./vmNames";

test("generateVmName includes provider suffix and random suffix", () => {
  assert.equal(generateVmName("provider-ED1D", "a1b2c3"), "vm-ed1d-a1b2c3");
});

test("generateVmName falls back to a valid provider segment", () => {
  assert.equal(generateVmName("----", "a1b2c3"), "vm-node-a1b2c3");
});

test("generateVmName creates provider API compatible names", () => {
  assert.match(generateVmName("provider-ED1D"), /^[a-z0-9][a-z0-9-]*[a-z0-9]$/);
});
