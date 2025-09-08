StreamPayment (EIP‑1620 inspired)

This package provides a minimal streaming payments contract for GLM on Polygon PoS.

- Rate‑per‑second vesting funded up‑front with GLM
- Recipient can withdraw vested funds
- Sender or recipient can terminate (refunds unvested to sender)
- Oracle can halt a stream (emergency stop) via `haltStream`
- Sender can extend runtime via `topUp(streamId, amount)` (extends stopTime)

Tooling: Hardhat with Polygon PoS target and a deploy script.

Core interfaces

- `createStream(address token, address recipient, uint256 deposit, uint128 ratePerSecond) -> streamId`
- `withdraw(uint256 streamId)` — transfers newly vested GLM to recipient
- `terminate(uint256 streamId)` — pays out vested to recipient and refunds rest to sender
- `haltStream(uint256 streamId)` — oracle clamp; stops further vesting
- `topUp(uint256 streamId, uint256 amount)` — increases deposit and extends `stopTime` by `amount / ratePerSecond`
- `streams(uint256 id) -> (token, sender, recipient, startTime, stopTime, ratePerSecond, deposit, withdrawn, halted)`

Recommended flow

1) Requestor computes `ratePerSecond` from provider pricing and resources.
2) Requestor deposits at least 1 hour of coverage (`deposit >= rate * 3600`).
3) Requestor calls provider `POST /api/v1/vms` with `stream_id` to start rental.
4) Requestor can call `topUp` periodically to keep the rental going indefinitely.
5) Provider may run a background task to withdraw vested funds and to stop VMs if runway is too low.

Deployment

- Env vars:
  - `POLYGON_RPC_URL` — Polygon PoS RPC endpoint
  - `PRIVATE_KEY` — deployer key
  - `GLM_TOKEN_ADDRESS` — ERC20 GLM address on Polygon
  - `ORACLE_ADDRESS` — optional; defaults to deployer address
- Commands:
  - `npm install`
  - `npx hardhat run scripts/deploy.js --network polygon`
- Output: Deployment info is written to `contracts/deployments/polygon.json`.

Notes

- Periodic withdrawal is not automated on‑chain; do it off‑chain with thresholds to minimize gas.
- Halting a stream via oracle stops accrual but does not auto‑terminate; sender/recipient can terminate to settle funds.
