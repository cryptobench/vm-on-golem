Streaming ABI

Shared Python package exporting the generated StreamPayment ABI used by
provider and requestor components. The ABI is copied from the compiled Hardhat
artifact; do not edit it by hand.

Contents:

- `golem_streaming_abi.STREAM_PAYMENT_ABI`
- `golem_streaming_abi.ERC20_ABI`

The StreamPayment contract is GLM-only. Integrations must pass the configured
GLM token address, approve GLM before create/top-up calls, and use native ETH
only for gas.

If the on-chain contract interface changes, update Solidity, compile contracts,
run `npm run abi:sync`, then run `npm run abi:check`.
