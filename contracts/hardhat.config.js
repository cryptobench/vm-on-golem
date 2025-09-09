require("dotenv").config();
require("@nomicfoundation/hardhat-toolbox");

const {
  POLYGON_RPC_URL,
  PRIVATE_KEY,
  ETHWARSAW_RPC_URL,
  ETHWARSAW_CHAIN_ID,
  KAOLIN_RPC_URL,
  KAOLIN_CHAIN_ID,
  L2_RPC_URL,
  L2_CHAIN_ID,
} = process.env;

module.exports = {
  solidity: "0.8.20",
  networks: {
    polygon: {
      url: POLYGON_RPC_URL || "https://polygon-rpc.com",
      accounts: PRIVATE_KEY ? [PRIVATE_KEY] : [],
    },
    // ETHWARSAW Holesky network (EVM-compatible)
    ethwarsaw: {
      url: ETHWARSAW_RPC_URL || "https://ethwarsaw.holesky.golemdb.io/rpc",
      // chainId is optional; if known, set ETHWARSAW_CHAIN_ID env var
      chainId: ETHWARSAW_CHAIN_ID ? Number(ETHWARSAW_CHAIN_ID) : undefined,
      accounts: PRIVATE_KEY ? [PRIVATE_KEY] : [],
    },
    // KAOLIN Holesky network (EVM-compatible)
    kaolin: {
      url: KAOLIN_RPC_URL || "https://kaolin.holesky.golemdb.io/rpc",
      // chainId is optional; if known, set KAOLIN_CHAIN_ID env var
      chainId: KAOLIN_CHAIN_ID ? Number(KAOLIN_CHAIN_ID) : undefined,
      accounts: PRIVATE_KEY ? [PRIVATE_KEY] : [],
    },
    // L2 Holesky network
    l2: {
      url: L2_RPC_URL || "https://l2.holesky.golemdb.io/rpc",
      chainId: L2_CHAIN_ID ? Number(L2_CHAIN_ID) : undefined,
      accounts: PRIVATE_KEY ? [PRIVATE_KEY] : [],
    },
  },
};
