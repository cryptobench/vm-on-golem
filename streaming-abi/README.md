# Golem Streaming ABI

Shared Python package exporting the StreamPayment and ERC20 ABIs used by both provider and requestor components. Centralizing the ABI eliminates drift and keeps integrations consistent.

## Files

- Module: `golem_streaming_abi/__init__.py`
  - Exports `STREAM_PAYMENT_ABI` and `ERC20_ABI`

## Update the ABI

1. Edit the ABI definitions in `golem_streaming_abi/__init__.py`.
2. If you add or rename contract functions/events, update downstream code that calls them:
   - Requestor: `requestor-server/requestor/payments/blockchain_service.py`
   - Provider: `provider-server/provider/payments/blockchain_service.py`
3. Run tests to validate:

```bash
# Fast path for only requestor/provider
poetry -C provider-server run pytest provider-server/tests
poetry -C requestor-server run pytest requestor-server/tests

# Or the full suite
make test
```

## Version bumps and dependency refresh

This package is consumed via a local path dependency with `develop = true` by both services. A bump isn’t strictly required for local development, but recommended to make lock refreshes explicit.

- Bump version:

```bash
poetry -C streaming-abi version patch  # or minor/major
```

- Refresh service locks (either):

```bash
# Option A: service‑local
poetry -C provider-server lock --no-update && poetry -C provider-server install --with dev
poetry -C requestor-server lock --no-update && poetry -C requestor-server install --with dev

# Option B: repo‑wide helper
make install
```

## Sanity checks

- Ensure `STREAM_PAYMENT_ABI` contains at least:
  - `createStream`, `withdraw`, `terminate`, `topUp`, `streams`
  - `StreamCreated` event
- Note: `createStream` and `topUp` are payable; pass ETH `value` when `token=0x000...0`.
- Ensure `ERC20_ABI` contains at least `approve` and `allowance` (ERC20 mode only; not used for native ETH).
- Test guarantees:
  - Requestor test `tests/payments/test_abi_contains_streams_and_topup.py` asserts presence of `streams` and `topUp`.

## Notes

- If the on‑chain contract interface changes (e.g., new parameters), make corresponding updates in the requestor/provider blockchain clients and add tests that exercise those paths.
- Consider adding additional ABI functions here if future flows require them (e.g., `pause`, `resume`).
