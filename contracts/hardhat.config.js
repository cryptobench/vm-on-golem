import "dotenv/config";

import hardhatEthersPlugin from "@nomicfoundation/hardhat-ethers";
import hardhatEthersChaiMatchersPlugin from "@nomicfoundation/hardhat-ethers-chai-matchers";
import hardhatMochaPlugin from "@nomicfoundation/hardhat-mocha";
import { defineConfig } from "hardhat/config";

const {
  PAYMENTS_RPC_URL,
  PRIVATE_KEY,
  KAOLIN_RPC_URL,
  KAOLIN_CHAIN_ID,
  HOODI_RPC_URL,
  SEPOLIA_RPC_URL,
  ETHERSCAN_API_KEY,
} = process.env;

const DEFAULT_KAOLIN_CHAIN_ID = 60138453025;
const DEFAULT_HOODI_CHAIN_ID = 560048;

export default defineConfig({
  plugins: [
    hardhatEthersPlugin,
    hardhatEthersChaiMatchersPlugin,
    hardhatMochaPlugin,
  ],
  solidity: {
    profiles: {
      default: {
        version: "0.8.20",
        settings: {
          optimizer: { enabled: true, runs: 200 },
          viaIR: true,
        },
      },
    },
  },
  networks: {
    hardhatMainnet: {
      type: "edr-simulated",
      chainType: "l1",
    },
    polygon: {
      type: "http",
      chainType: "l1",
      url: PAYMENTS_RPC_URL || "https://polygon-rpc.com",
      accounts: PRIVATE_KEY ? [PRIVATE_KEY] : [],
    },
    // KAOLIN Hoodi network (EVM-compatible)
    kaolin: {
      type: "http",
      chainType: "generic",
      url: KAOLIN_RPC_URL || "https://kaolin.hoodi.arkiv.network/rpc",
      chainId: Number(KAOLIN_CHAIN_ID || DEFAULT_KAOLIN_CHAIN_ID),
      accounts: PRIVATE_KEY ? [PRIVATE_KEY] : [],
    },
    sepolia: {
      type: "http",
      chainType: "l1",
      url: SEPOLIA_RPC_URL || "https://rpc.sepolia.org",
      chainId: 11155111,
      accounts: PRIVATE_KEY ? [PRIVATE_KEY] : [],
    },
    hoodi: {
      type: "http",
      chainType: "l1",
      url: HOODI_RPC_URL || "https://rpc.hoodi.ethpandaops.io",
      chainId: DEFAULT_HOODI_CHAIN_ID,
      accounts: PRIVATE_KEY ? [PRIVATE_KEY] : [],
    },
  },
  etherscan: {
    apiKey: ETHERSCAN_API_KEY || "",
    customChains: [
      {
        network: "hoodi",
        chainId: DEFAULT_HOODI_CHAIN_ID,
        urls: {
          apiURL: "https://api.etherscan.io/v2/api",
          browserURL: "https://hoodi.etherscan.io",
        },
      },
    ],
  },
});
