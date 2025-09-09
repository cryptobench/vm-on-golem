StreamPayment (EIP‑1620 inspired)

This package provides a minimal streaming payments contract supporting native ETH (token=0x0) and ERC20 tokens.

- Rate‑per‑second vesting funded up‑front (ETH or ERC20)
- Recipient can withdraw vested funds
- Sender or recipient can terminate (refunds unvested to sender)
- Oracle can halt a stream (emergency stop) via `haltStream`
- Sender can extend runtime via `topUp(streamId, amount)` (extends stopTime)

Tooling: Hardhat with EVM networks (Kaolin, Polygon) and a deploy script.

Core interfaces

- `createStream(address token, address recipient, uint256 deposit, uint128 ratePerSecond) -> streamId` (payable when token=0x0)
- `withdraw(uint256 streamId)` — transfers newly vested funds to recipient
- `terminate(uint256 streamId)` — pays out vested to recipient and refunds rest to sender
- `haltStream(uint256 streamId)` — oracle clamp; stops further vesting
- `topUp(uint256 streamId, uint256 amount)` — increases deposit and extends `stopTime` by `amount / ratePerSecond` (payable when token=0x0; `msg.value` must equal `amount`)
- `streams(uint256 id) -> (token, sender, recipient, startTime, stopTime, ratePerSecond, deposit, withdrawn, halted)`

Recommended flow

1) Requestor computes `ratePerSecond` from provider pricing and resources.
2) Requestor deposits at least 1 hour of coverage (`deposit >= rate * 3600`). For ETH mode, send as `msg.value`.
3) Requestor calls provider `POST /api/v1/vms` with `stream_id` to start rental.
4) Requestor can call `topUp` periodically to keep the rental going indefinitely.
5) Provider may run a background task to withdraw vested funds and to stop VMs if runway is too low.

Deployment

Polygon PoS

- Env vars:
  - `POLYGON_RPC_URL` — Polygon PoS RPC endpoint
  - `PRIVATE_KEY` — deployer key (with MATIC for gas)
  - `GLM_TOKEN_ADDRESS` — ERC20 token address on Polygon (use only for ERC20 mode)
  - `ORACLE_ADDRESS` — optional; defaults to deployer address
- Commands:
  - `npm install`
  - `npx hardhat run scripts/deploy.js --network polygon`
- Output: Deployment info is written to `contracts/deployments/<network>.json`.

ETHWARSAW (Holesky) test network

- Network info
  - RPC (HTTP): `https://ethwarsaw.holesky.golemdb.io/rpc`
  - RPC (WS): `wss://ethwarsaw.holesky.golemdb.io/rpc/ws`
  - Faucet: `https://ethwarsaw.holesky.golemdb.io/faucet/`
  - Explorer: `https://explorer.ethwarsaw.holesky.golemdb.io`
- Env vars:
  - `ETHWARSAW_RPC_URL` — defaults to the HTTP RPC above
  - `PRIVATE_KEY` — deployer key (fund with faucet ETH for gas)
  - `GLM_TOKEN_ADDRESS` — ERC20 token address on this network (optional). For native ETH mode leave unset and pass `0x000...0`.
  - `ORACLE_ADDRESS` — optional; defaults to deployer address
- Deploy MockGLM (optional, for testing):
  ```bash
  npm install
  npx hardhat run scripts/deploy_mock_glm.js --network ethwarsaw
  # Record MockGLM address from deployments/ethwarsaw-mockglm.json
  export GLM_TOKEN_ADDRESS=<MockGLM_address>
  ```
- Deploy StreamPayment:
  ```bash
  ETHWARSAW_RPC_URL=https://ethwarsaw.holesky.golemdb.io/rpc \
  # For ETH mode, you may omit GLM_TOKEN_ADDRESS and pass zero from clients
  PRIVATE_KEY=0x... \
  npx hardhat run scripts/deploy.js --network ethwarsaw
  ```
- Output: Deployment info is written to `contracts/deployments/<network>.json`.

KAOLIN (Holesky) test network

- Network info
  - RPC (HTTP): `https://kaolin.holesky.golemdb.io/rpc`
  - RPC (WS): `wss://kaolin.holesky.golemdb.io/rpc/ws`
  - Faucet: `https://kaolin.holesky.golemdb.io/faucet/`
  - Explorer: `https://explorer.kaolin.holesky.golemdb.io`
  - Network ID (chainId): `60138453025`
- Env vars:
  - `KAOLIN_RPC_URL` — defaults to the HTTP RPC above
  - `KAOLIN_CHAIN_ID` — optional; set to `60138453025` to avoid chainId mismatches
  - `PRIVATE_KEY` — deployer key (fund with faucet ETH for gas)
  - `GLM_TOKEN_ADDRESS` — ERC20 token address on this network (optional). For native ETH mode leave unset and pass `0x000...0`.
  - `ORACLE_ADDRESS` — optional; defaults to deployer address
- Deploy MockGLM (optional, for testing):
  ```bash
  npm install
  npx hardhat run scripts/deploy_mock_glm.js --network kaolin
  # Record MockGLM address from deployments/kaolin-mockglm.json
  export GLM_TOKEN_ADDRESS=<MockGLM_address>
  ```
- Deploy StreamPayment:
  ```bash
  KAOLIN_RPC_URL=https://kaolin.holesky.golemdb.io/rpc \
  KAOLIN_CHAIN_ID=60138453025 \
  GLM_TOKEN_ADDRESS=$GLM_TOKEN_ADDRESS \
  PRIVATE_KEY=0x... \
  npx hardhat run scripts/deploy.js --network kaolin
  ```
- Output: Deployment info is written to `contracts/deployments/<network>.json` (e.g., `kaolin.json`).

L2 (Holesky) test network

- Network info
  - RPC (HTTP): `https://l2.holesky.golemdb.io/rpc`
  - RPC (WS): `wss://l2.holesky.golemdb.io/rpc/ws`
  - Faucet: `https://l2.holesky.golemdb.io/faucet/`
  - Explorer: `https://explorer.l2.holesky.golemdb.io`
  - Network ID (chainId): `393530`
- Env vars:
  - `L2_RPC_URL` — defaults to the HTTP RPC above
  - `L2_CHAIN_ID` — optional; set to `393530`
  - `PRIVATE_KEY` — deployer key (fund with faucet ETH for gas)
  - `GLM_TOKEN_ADDRESS` — ERC20 token address (optional). For native ETH mode, pass `0x000...0` from clients and leave this unset.
  - `ORACLE_ADDRESS` — optional; defaults to deployer address
- Deploy StreamPayment (native ETH mode):
  ```bash
  L2_RPC_URL=https://l2.holesky.golemdb.io/rpc \
  L2_CHAIN_ID=393530 \
  PRIVATE_KEY=0x... \
  npx hardhat run scripts/deploy.js --network l2
  ```
- Output: Deployment info is written to `contracts/deployments/<network>.json` (e.g., `l2.json`).

Notes

- Periodic withdrawal is not automated on‑chain; do it off‑chain with thresholds to minimize gas.
- Halting a stream via oracle stops accrual but does not auto‑terminate; sender/recipient can terminate to settle funds.
