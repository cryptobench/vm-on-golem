import assert from "node:assert/strict";
import test from "node:test";

import {
  formatTokenAmount,
  parseLeaseQuoteBody,
  totalDepositForProviderDeposit,
} from "./paymentStreams";

test("lease quote parser preserves unsafe integer fields as strings", () => {
  const body = `{
    "provider_address":"0x4D30ec093423Ed51a726587D591C0fcc05A9ed1D",
    "chain_id":560048,
    "contract_address":"0xb5a225b2f82D3eFe743D95bA7Fe3BbC475C0a12E",
    "glm_token_address":"0x55555555555556AcFf9C332Ed151758858bd7a26",
    "lease_id":"0x${"11".repeat(32)}",
    "terms_hash":"0x${"22".repeat(32)}",
    "provider_rate_per_second_wei":22162410309280001,
    "provider_deposit_wei":57492991521653762592000,
    "min_runway_seconds":2592000,
    "quote_expires_at":1778964865,
    "signature":"0xsignature"
  }`;

  const quote = parseLeaseQuoteBody(body);

  assert.equal(quote.provider_rate_per_second_wei, "22162410309280001");
  assert.equal(quote.provider_deposit_wei, "57492991521653762592000");
});

test("formats quote token amount without display-side rounding", () => {
  assert.equal(formatTokenAmount(78_960_000_000_000_000_000n, 18), "78.96");
  assert.equal(formatTokenAmount(78_960_123_456_789_000_000n, 18), "78.960123");
});

test("total deposit helper matches approval amount with donation", () => {
  assert.equal(totalDepositForProviderDeposit(1_000n, 150), 1_015n);
  assert.equal(totalDepositForProviderDeposit(1_001n, 150), 1_016n);
});
