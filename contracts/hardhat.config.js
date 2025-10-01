require("dotenv").config();
require("@nomicfoundation/hardhat-toolbox");

const {
  POLYGON_RPC_URL,
  PRIVATE_KEY,
  KAOLIN_RPC_URL,
  KAOLIN_CHAIN_ID,
  L2_RPC_URL,
  L2_CHAIN_ID,
} = process.env;

const DEFAULT_KAOLIN_CHAIN_ID = 60138453025;
const DEFAULT_L2_CHAIN_ID = 393530;

module.exports = {
  solidity: "0.8.20",
  networks: {
    polygon: {
      url: POLYGON_RPC_URL || "https://polygon-rpc.com",
      accounts: PRIVATE_KEY ? [PRIVATE_KEY] : [],
    },
    // KAOLIN Hoodi network (EVM-compatible)
    kaolin: {
      url: KAOLIN_RPC_URL || "https://kaolin.hoodi.arkiv.network/rpc",
      chainId: Number(KAOLIN_CHAIN_ID || DEFAULT_KAOLIN_CHAIN_ID),
      accounts: PRIVATE_KEY ? [PRIVATE_KEY] : [],
    },
    // L2 Hoodi network
    l2: {
      url: L2_RPC_URL || "https://l2.hoodi.arkiv.network/rpc",
      chainId: Number(L2_CHAIN_ID || DEFAULT_L2_CHAIN_ID),
      accounts: PRIVATE_KEY ? [PRIVATE_KEY] : [],
    },
  },
};
