Streaming ABI

Shared Python package exporting the StreamPayment ABI used by provider and
requestor components. Centralizing the ABI prevents drift between services.

Contents:

- `golem_streaming_abi.STREAM_PAYMENT_ABI`
- `golem_streaming_abi.ERC20_ABI`

The StreamPayment contract is GLM-only. Integrations must pass the configured
GLM token address, approve GLM before create/top-up calls, and use native ETH
only for gas.

If the on-chain contract interface changes, update the provider/requestor
blockchain clients and the ABI guard tests together.
