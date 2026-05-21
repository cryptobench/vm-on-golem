import assert from "node:assert/strict";
import test from "node:test";

import { computeEstimate, type ProviderAd } from "./api";
import { clampResizeResources, computeResizeLimits } from "./vmResize";

test("resize limits include current allocation plus provider availability", () => {
  const limits = computeResizeLimits(
    { cpu: 2, memory: 4, storage: 20 },
    {
      resources: {
        available: { cpu: 3, memory: 9, storage: 25 },
        total: { cpu: 8, memory: 16, storage: 100 },
      },
    },
  );

  assert.deepEqual(limits, { cpu: 5, memory: 13, storage: 45 });
});

test("resize resources clamp to limits without power-of-two restrictions", () => {
  const current = { cpu: 2, memory: 4, storage: 20 };
  const limits = { cpu: 5, memory: 13, storage: 45 };

  assert.deepEqual(
    clampResizeResources({ cpu: 3, memory: 9, storage: 25 }, current, limits),
    { cpu: 3, memory: 9, storage: 25 },
  );
  assert.deepEqual(
    clampResizeResources({ cpu: 9, memory: 99, storage: 10 }, current, limits),
    { cpu: 5, memory: 13, storage: 20 },
  );
});

test("zero GLM pricing is treated as unavailable for payment rate fallback", () => {
  const estimate = computeEstimate(
    {
      provider_id: "0xprovider",
      ip_address: "127.0.0.1",
      country: "DK",
      created_at: "",
      updated_at: "",
      resources: { cpu: 8, memory: 16, storage: 100 },
      pricing: {
        usd_per_core_month: 1,
        usd_per_gb_ram_month: 1,
        usd_per_gb_storage_month: 0.1,
        glm_per_core_month: 0,
        glm_per_gb_ram_month: 0,
        glm_per_gb_storage_month: 0,
      },
    } as ProviderAd,
    3,
    9,
    25,
  );

  assert.equal(estimate.lease_usd_per_month, 14.5);
  assert.equal(estimate.donation_usd_per_month, 0.2175);
  assert.equal(estimate.usd_per_month, 14.7175);
  assert.equal(estimate.glm_per_month, undefined);
});

test("zero requestor donation leaves estimate equal to provider lease subtotal", () => {
  const estimate = computeEstimate(
    {
      provider_id: "0xprovider",
      ip_address: "127.0.0.1",
      country: "DK",
      created_at: "",
      updated_at: "",
      resources: { cpu: 8, memory: 16, storage: 100 },
      pricing: {
        usd_per_core_month: 1,
        usd_per_gb_ram_month: 1,
        usd_per_gb_storage_month: 0.1,
        glm_per_core_month: 10,
        glm_per_gb_ram_month: 2,
        glm_per_gb_storage_month: 0.5,
      },
    } as ProviderAd,
    3,
    9,
    25,
    0,
  );

  assert.equal(estimate.lease_usd_per_month, 14.5);
  assert.equal(estimate.donation_usd_per_month, 0);
  assert.equal(estimate.usd_per_month, 14.5);
  assert.equal(estimate.lease_glm_per_month, 60.5);
  assert.equal(estimate.donation_glm_per_month, 0);
  assert.equal(estimate.glm_per_month, 60.5);
});
