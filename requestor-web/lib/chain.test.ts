import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  getPaymentNetworkErrorMessage,
  getPaymentsChain,
  normalizeChainId,
  PaymentNetworkError,
  switchToPaymentsNetwork,
} from "./chain";

describe("payments chain helpers", () => {
  it("normalizes decimal and hex chain ids to lowercase hex", () => {
    assert.equal(normalizeChainId("560048"), "0x88bb0");
    assert.equal(normalizeChainId("0x088BB0"), "0x88bb0");
    assert.equal(normalizeChainId(560048), "0x88bb0");
  });

  it("prefers persisted settings over environment defaults", () => {
    const chain = getPaymentsChain({
      evm_chain_id: "560048",
      evm_chain_name: "Local Payments",
      evm_rpc_url: "https://payments.example/rpc",
      evm_explorer_url: "https://payments.example/explorer",
    });

    assert.equal(chain.chainId, "0x88bb0");
    assert.equal(chain.chainName, "Local Payments");
    assert.deepEqual(chain.rpcUrls, ["https://payments.example/rpc"]);
    assert.deepEqual(chain.blockExplorerUrls, ["https://payments.example/explorer"]);
  });

  it("formats wrong-network and explicit rpc failures as actionable messages", () => {
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
        new PaymentNetworkError(
          "rpc_unhealthy",
          "MetaMask cannot reach the payments RPC endpoint.",
        ),
        chain,
      ),
      /https:\/\/payments\.example\/rpc/,
    );
  });

  it("does not misclassify provider fetch failures as wallet rpc failures", () => {
    const chain = getPaymentsChain({
      evm_chain_name: "Golem Payments",
      evm_rpc_url: "https://payments.example/rpc",
    });

    assert.equal(
      getPaymentNetworkErrorMessage(
        new Error("Provider http://192.168.2.1:7466 is unreachable while loading the lease quote."),
        chain,
      ),
      "Provider http://192.168.2.1:7466 is unreachable while loading the lease quote.",
    );
  });

  it("prompts a wallet network switch before continuing on the wrong chain", async () => {
    const chain = getPaymentsChain({
      evm_chain_id: "0x88bb0",
      evm_chain_name: "Golem Payments",
      evm_rpc_url: "https://payments.example/rpc",
    });
    const calls: string[] = [];
    let currentChainId = "0x1";
    const ethereum = {
      request: async ({ method, params }: { method: string; params?: any[] }) => {
        calls.push(method);
        if (method === "eth_chainId") return currentChainId;
        if (method === "wallet_switchEthereumChain") {
          currentChainId = params?.[0]?.chainId;
          return null;
        }
        throw new Error(`unexpected method ${method}`);
      },
    };

    await switchToPaymentsNetwork(ethereum, chain);

    assert.deepEqual(calls, [
      "eth_chainId",
      "wallet_switchEthereumChain",
      "eth_chainId",
    ]);
  });

  it("adds the payments network only when the wallet does not know it", async () => {
    const chain = getPaymentsChain({
      evm_chain_id: "0x88bb0",
      evm_chain_name: "Golem Payments",
      evm_rpc_url: "https://payments.example/rpc",
    });
    const calls: string[] = [];
    let currentChainId = "0x1";
    const ethereum = {
      request: async ({ method, params }: { method: string; params?: any[] }) => {
        calls.push(method);
        if (method === "eth_chainId") return currentChainId;
        if (method === "wallet_switchEthereumChain") {
          if (params?.[0]?.chainId === chain.chainId && calls.length === 2) {
            const error = new Error("unknown chain") as Error & { code: number };
            error.code = 4902;
            throw error;
          }
          currentChainId = params?.[0]?.chainId;
          return null;
        }
        if (method === "wallet_addEthereumChain") return null;
        throw new Error(`unexpected method ${method}`);
      },
    };

    await switchToPaymentsNetwork(ethereum, chain);

    assert.deepEqual(calls, [
      "eth_chainId",
      "wallet_switchEthereumChain",
      "wallet_addEthereumChain",
      "wallet_switchEthereumChain",
      "eth_chainId",
    ]);
  });
});
