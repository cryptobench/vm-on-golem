import "dotenv/config";

import hardhatEthersPlugin from "@nomicfoundation/hardhat-ethers";
import hardhatEthersChaiMatchersPlugin from "@nomicfoundation/hardhat-ethers-chai-matchers";
import hardhatMochaPlugin from "@nomicfoundation/hardhat-mocha";
import { defineConfig } from "hardhat/config";

const {
  POLYGON_RPC_URL,
  PRIVATE_KEY,
  KAOLIN_RPC_URL,
  KAOLIN_CHAIN_ID,
  L2_RPC_URL,
  L2_CHAIN_ID,
  HOODI_RPC_URL,
  SEPOLIA_RPC_URL,
  ETHERSCAN_API_KEY,
} = process.env;

const DEFAULT_KAOLIN_CHAIN_ID = 60138453025;
const DEFAULT_L2_CHAIN_ID = 393530;
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
      url: POLYGON_RPC_URL || "https://polygon-rpc.com",
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
    // L2 Hoodi network
    l2: {
      type: "http",
      chainType: "generic",
      url: L2_RPC_URL || "https://l2.hoodi.arkiv.network/rpc",
      chainId: Number(L2_CHAIN_ID || DEFAULT_L2_CHAIN_ID),
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
      url: HOODI_RPC_URL || "https://ethereum-hoodi-rpc.publicnode.com",
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
