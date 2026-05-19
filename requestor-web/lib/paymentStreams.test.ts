import assert from "node:assert/strict";
import test from "node:test";

import { parseLeaseQuoteBody } from "./paymentStreams";

test("lease quote parser preserves unsafe integer fields as strings", () => {
  const body = `{
    "provider_address":"0x4D30ec093423Ed51a726587D591C0fcc05A9ed1D",
    "chain_id":560048,
    "contract_address":"0x479044F8A58276DC15d0d924a6A92Ec663877D00",
    "glm_token_address":"0x55555555555556AcFf9C332Ed151758858bd7a26",
    "lease_id":"0x${"11".repeat(32)}",
    "terms_hash":"0x${"22".repeat(32)}",
    "rate_per_second_wei":22162410309280001,
    "min_deposit_wei":57492991521653762592000,
    "min_runway_seconds":2592000,
    "quote_expires_at":1778964865,
    "signature":"0xsignature"
  }`;

  const quote = parseLeaseQuoteBody(body);

  assert.equal(quote.rate_per_second_wei, "22162410309280001");
  assert.equal(quote.min_deposit_wei, "57492991521653762592000");
});
