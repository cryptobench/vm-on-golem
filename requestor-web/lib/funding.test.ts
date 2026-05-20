import test from "node:test";
import assert from "node:assert/strict";
import {
  explorerTxUrl,
  formatCompactUnits,
  formatNativeBalance,
  formatTokenBalance,
} from "./funding";

test("formatCompactUnits trims trailing zeros and caps precision", () => {
  assert.equal(formatCompactUnits(1234567890000000000n, 18), "1.234567");
  assert.equal(formatCompactUnits(1000000000000000000n, 18), "1");
});

test("format balance helpers include expected symbols", () => {
  assert.equal(formatNativeBalance(2500000000000000n), "0.0025 ETH");
  assert.equal(formatTokenBalance(1000000000000000000000n), "1000 tGLM");
});

test("explorerTxUrl joins tx links without double slashes", () => {
  assert.equal(
    explorerTxUrl("https://hoodi.etherscan.io/", "0xabc"),
    "https://hoodi.etherscan.io/tx/0xabc",
  );
});
