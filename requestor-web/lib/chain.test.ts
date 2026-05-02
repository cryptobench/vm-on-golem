import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  getPaymentNetworkErrorMessage,
  getPaymentsChain,
  normalizeChainId,
  PaymentNetworkError,
} from "./chain";

describe("payments chain helpers", () => {
  it("normalizes decimal and hex chain ids to lowercase hex", () => {
    assert.equal(normalizeChainId("393530"), "0x6013a");
    assert.equal(normalizeChainId("0x06013A"), "0x6013a");
    assert.equal(normalizeChainId(393530), "0x6013a");
  });

  it("prefers persisted settings over environment defaults", () => {
    const chain = getPaymentsChain({
      evm_chain_id: "393530",
      evm_chain_name: "Local Payments",
      evm_rpc_url: "https://payments.example/rpc",
      evm_explorer_url: "https://payments.example/explorer",
    });

    assert.equal(chain.chainId, "0x6013a");
    assert.equal(chain.chainName, "Local Payments");
    assert.deepEqual(chain.rpcUrls, ["https://payments.example/rpc"]);
    assert.deepEqual(chain.blockExplorerUrls, ["https://payments.example/explorer"]);
  });

  it("formats wrong-network and rpc failures as actionable messages", () => {
    const chain = getPaymentsChain({
      evm_chain_name: "Golem Payments",
      evm_rpc_url: "https://payments.example/rpc",
    });

    assert.match(
      getPaymentNetworkErrorMessage(
        new PaymentNetworkError("wrong_network", "wrong chain"),
        chain,
      ),
      /Switch MetaMask to Golem Payments/,
    );
    assert.match(
      getPaymentNetworkErrorMessage(
        new Error("could not coalesce error: RPC endpoint returned too many errors"),
        chain,
      ),
      /https:\/\/payments\.example\/rpc/,
    );
  });
});
