# Contributing

Thanks for contributing to VM-on-Golem! This document highlights workflow tips and checklists specific to this monorepo.

## General

- Keep changes small, focused, and scoped to a single package when possible.
- Ensure `make test` passes locally.
- Follow per-service coding style (Black 88 cols, isort profile=black, type hints on new/changed code).

## Streaming Payments – ABI Changes Checklist

If you change the on-chain StreamPayment interface or how we interact with it:

1. Update the shared ABI
   - Edit `streaming-abi/golem_streaming_abi/__init__.py`.
   - Ensure it includes all required functions/events (`createStream`, `withdraw`, `terminate`, `topUp`, `streams`, `StreamCreated`).
2. Update clients
   - Requestor: `requestor-server/requestor/payments/blockchain_service.py`.
   - Provider: `provider-server/provider/payments/blockchain_service.py`.
3. Update tests
   - Requestor has a guard test (`tests/payments/test_abi_contains_streams_and_topup.py`).
   - Add/adjust tests to cover new flows.
4. Refresh dependencies
   - Option A: `poetry -C provider-server lock --no-update && poetry -C provider-server install --with dev`.
   - Option B: `poetry -C requestor-server lock --no-update && poetry -C requestor-server install --with dev`.
   - Or run `make install`.
5. Verify
   - Run `make test`.

See `streaming-abi/README.md` for detailed instructions.

## Provider/Requestor Streaming Guidelines

- Requestor should never auto-create streams implicitly in production; streams are created explicitly via CLI and passed as `stream_id`.
- Requestor prefers provider-advertised contract/token addresses from `GET /api/v1/provider/info`.
- Provider persists VM→stream mappings and honors monitor intervals for withdrawals; keep intervals conservative.

## Pull Requests

Please include:

- Summary of changes and rationale.
- Affected packages/services.
- Tests added/updated.
- Any config or doc updates.
- For ABI changes, confirm the checklist above.

Thanks for helping improve VM-on-Golem!
