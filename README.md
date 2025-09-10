# VM-on-Golem

Run, discover, and manage virtual machines on the Golem Network. This monorepo contains the Requestor CLI, Provider service, Discovery service, a Port Checker utility, streaming payments integration, and GUI shells.

Quick links:
- Contracts and deployment: `contracts/README.md`
- Provider service and config: `provider-server/README.md`
- Requestor CLI usage: `requestor-server/README.md`
- Port checker service: `port-checker-server/README.md`

## Roles

- Requestors pay to rent machines. They use the `golem` CLI to discover providers, open a payment stream, create VMs, and connect via SSH. Costs accrue per second while the VM runs.
- Providers rent out their machines to earn. They run the `golem-provider` service, advertise resources, host VMs, and can withdraw vested funds from incoming payment streams.

## Getting Started

- Prerequisites: Python 3.11+, Multipass (for VMs).
- Install the Requestor CLI (most users):
  - `pip install request-vm-on-golem`
  - Run commands via `golem ...` (see cheatsheet below).
- Install the Provider service (if you plan to host VMs):
  - `pip install golem-vm-provider`
  - Start with `golem-provider start` (add `--network testnet|mainnet` as needed).
- Optional utilities:
  - Port checker: `pip install golem-port-checker` → start with `port-checker`
  - Legacy centralized discovery (not required): `pip install golem-vm-discovery`

Environment modes (optional):
- Provider: `GOLEM_PROVIDER_ENVIRONMENT=development|production`
- Requestor: `GOLEM_REQUESTOR_ENVIRONMENT=development|production`
- Discovery: `GOLEM_DISCOVERY_DEBUG=true` for verbose logs

## Streaming Payments (Native ETH on L2)

The system integrates a minimal EIP‑1620–style StreamPayment contract to gate VM runtime with pay‑as‑you‑go funding in native ETH (or GLM). Key points:
- Provider only creates/keeps VMs running when a valid funded stream to the provider exists.
- Requestors can open, top up, and inspect streams; providers can withdraw vested funds.
- Default contract addresses and RPCs are provided via per‑service configs; both services prefer provider‑advertised addresses to avoid mismatches.

References:
- On‑chain contracts and deployments: `contracts/`
- Shared ABI package: `streaming-abi/`
- Provider streaming config: `provider-server/README.md`
- Requestor streaming commands: `requestor-server/README.md`

## Cheatsheet: Requestor CLI (`golem`)

Audience: users who pay to rent compute on providers.

Install: `pip install request-vm-on-golem` then run `golem ...`.
From source/dev: use Poetry; see Development Workflows.

- `golem --version`
  - Usage: show CLI version.
  - Output: `Requestor VM on Golem CLI version <x.y.z>`.

- `golem vm providers [--cpu N] [--memory GB] [--storage GB] [--country CC] [--payments-network NAME] [--all-payments] [--json] [--network testnet|mainnet]`
  - Usage: list discoverable providers with optional filters; shows pricing estimates when a full spec is provided.
  - Output: table or JSON: `{ providers: [...] }` with provider metadata and optional `estimate`.

- `golem vm create <name> --provider-id 0x... --cpu N --memory GB --storage GB [--stream-id ID] [--hours H] [--yes] [--network testnet|mainnet]`
  - Usage: create a VM on a specific provider; if `--stream-id` not given and streaming is enabled, opens a stream with `--hours` of deposit.
  - Output: progress messages; on success the VM is recorded in the local DB. When stream is auto‑opened, prints JSON `{ stream_id, rate_per_second_wei, deposit_wei }` during creation.

- `golem vm ssh <name>` (alias: `golem vm connect <name>`)
  - Usage: open SSH to the VM via provider’s proxy with the managed key.
  - Output: connects the terminal to the VM (no JSON).

- `golem vm info <name> [--json]`
  - Usage: show VM details from the local DB and provider.
  - Output: table or JSON with status, provider IP, SSH port, CPU, memory, disk.

- `golem vm start <name>` / `golem vm stop <name>`
  - Usage: start or stop a VM on the provider. Stop also attempts to settle/terminate the stream.
  - Output: human‑readable status summary.

- `golem vm destroy <name>` (alias: `golem vm delete <name>`)
  - Usage: destroy VM on the provider and clean up local state; terminates the stream best‑effort.
  - Output: human‑readable status summary.

- `golem vm purge [--force]` (interactive confirm)
  - Usage: destroy all locally known VMs; attempts on‑chain termination per VM.
  - Output: per‑VM results and a summary table.

- `golem vm list [--json]`
  - Usage: list VMs tracked in the local DB.
  - Output: table or JSON `{ vms: [...] }`.

- `golem vm stats <name>`
  - Usage: live CPU/memory/disk usage view (updates every 2s until Ctrl+C).
  - Output: live terminal display.

- Streams: `golem vm stream ...`
  - `open --provider-id 0x... --cpu N --memory GB --storage GB --hours H`
    - Open a stream with deposit sized for `H` hours at provider’s rates.
    - Output: JSON `{ stream_id, rate_per_second_wei, deposit_wei }`.
  - `topup --stream-id ID (--glm AMOUNT | --hours H)`
    - Add funds either by GLM/ETH amount or hours at prior rate.
    - Output: JSON `{ stream_id, topped_up_wei, tx }`.
  - `status <name> [--json]`
    - Status via provider for VM by name.
    - Output: human table or JSON with `chain` and `computed` fields.
  - `inspect --stream-id ID [--json]`
    - Inspect a stream directly on‑chain.
    - Output: human table or JSON with `chain` and `computed` fields.

- Wallet: `golem wallet faucet`
  - Usage: request test L2 ETH/GLM funds for the requestor address (only on faucet‑enabled profiles).
  - Output: JSON `{ address, tx | null }` or a `faucet_disabled` error object.

- Server API: `golem server api [--host 127.0.0.1] [--port 8000] [--reload]`
  - Usage: run requestor’s FastAPI server (used by GUIs or automation).
  - Output: uvicorn logs; OpenAPI at `http://<host>:<port>/`.

Config tips (env prefix `GOLEM_REQUESTOR_`):
- `ENVIRONMENT`, `NETWORK` (`testnet|mainnet` discovery filter), `PAYMENTS_NETWORK` (e.g., `l2.holesky`), `polygon_rpc_url`, `stream_payment_address`, `glm_token_address`.
See `requestor-server/README.md` for details and development ergonomics.

## Cheatsheet: Provider CLI (`golem-provider`)

Audience: users who rent out their machines to earn.

Install: `pip install golem-vm-provider` then run `golem-provider ...`.
From source/dev: use Poetry; see Development Workflows.

- `golem-provider start [--no-verify-port] [--network testnet|mainnet]`
  - Usage: start the provider FastAPI server; reads `.env` or `.env.dev` if `GOLEM_PROVIDER_ENVIRONMENT=development`.
  - Output: uvicorn logs plus environment echo and port verification.

- Pricing: `golem-provider pricing ...`
  - `show`
    - Show current per‑unit USD and GLM prices plus example monthly totals.
    - Output: human‑readable table with examples.
  - `set --usd-per-core <USD> --usd-per-mem <USD> --usd-per-disk <USD> [--dev]`
    - Persist USD pricing to `.env(.dev)`; GLM rates auto‑recalculated.
    - Output: confirmation and example costs.

- Streams: `golem-provider streams ...`
  - `list [--json]`
    - List mapped VM↔stream pairs with remaining time and withdrawable amounts.
    - Output: table or JSON `{ streams: [...] }`.
  - `show <vm_id> [--json]`
    - Show one VM’s stream details.
    - Output: single‑row table or JSON with `chain`, `computed`, `verified`.
  - `earnings [--json]`
    - Summarize withdrawable totals (ETH/GLM) and per‑stream items.
    - Output: human tables or structured JSON `{ streams, totals }`.
  - `withdraw [--vm-id <id> | --all]`
    - Withdraw vested funds; attempts faucet on testnets for gas.
    - Output: per‑stream results with tx hashes.

- Wallet: `golem-provider wallet faucet-l2`
  - Usage: request test L2 ETH for the provider’s address when enabled.
  - Output: faucet tx hash or a message that faucet is disabled.

- Config: `golem-provider config ...`
  - `withdraw [--enable true|false] [--interval SECONDS] [--min-wei WEI] [--dev]`
    - Configure auto‑withdraw behavior and persist to `.env(.dev)`.
  - `monitor [--enable true|false] [--interval SECONDS] [--min-remaining SECONDS] [--dev]`
    - Configure on‑provider stream monitor thresholds.

Important env (prefix `GOLEM_PROVIDER_`):
- Networking: `HOST`, `PORT`, `PORT_RANGE_START`, `PORT_RANGE_END`, `PUBLIC_IP`.
- Discovery: `DISCOVERY_URL`, `ADVERTISEMENT_INTERVAL`, `NETWORK` annotation (`testnet|mainnet`).
- Pricing: `PRICE_USD_PER_CORE_MONTH`, `PRICE_USD_PER_GB_RAM_MONTH`, `PRICE_USD_PER_GB_STORAGE_MONTH`.
- Streaming: `POLYGON_RPC_URL`, `STREAM_PAYMENT_ADDRESS`, `GLM_TOKEN_ADDRESS`, monitor/withdraw toggles and intervals.
See `provider-server/README.md` for full documentation.

## Optional: Legacy Discovery Server

- The old centralized discovery server is available for advanced setups and testing, but is not required for normal use.
- Install (optional): `pip install golem-vm-discovery`, run with `golem-discovery`.
- For details, see `discovery-server/README.md`.

## Cheatsheet: Port Checker (`port-checker`)

- Install: `pip install golem-port-checker`
- `port-checker`
  - Usage: start the port checker service (default `0.0.0.0:9000`).
  - Output: uvicorn logs; OpenAPI at `/docs`.
- API:
  - `POST /check-ports` with `{ provider_ip, ports[] }` → JSON per‑port accessibility and summary.
  - `GET /health` → `{ "status": "ok" }`.
- Env:
  - `PORT_CHECKER_HOST`, `PORT_CHECKER_PORT`, `PORT_CHECK_RETRIES`, `PORT_CHECK_RETRY_DELAY`, `PORT_CHECK_TIMEOUT`, `PORT_CHECKER_DEBUG`.
See `port-checker-server/README.md` for examples and systemd usage.

## Repository Structure

- `discovery-server/` – FastAPI discovery service (`golem-discovery`)
- `provider-server/` – Provider API/CLI (`golem-provider`)
- `requestor-server/` – Requestor CLI/API (`golem`)
- `port-checker-server/` – Port checker FastAPI utility (`port-checker`)
- `provider-gui/`, `requestor-gui/` – Electron dev shells for GUIs
- `streaming-abi/` – Shared ABI package
- `scripts/` – Utilities (e.g., version bumps)

## Packaging GUI + CLI (Single Installer)

Goal: ship an installer (EXE/DMG/PKG/DEB) that includes the Electron GUI and a ready-to-use `golem-provider` CLI.

Build steps:
- Build standalone Provider CLI (PyInstaller):
  - `python scripts/build_provider_cli.py --onefile`
  - This stages binaries under `provider-gui/resources/cli/<platform>/golem-provider[.exe]`.
- Build Electron installers (from `provider-gui/`):
  - Windows (NSIS, adds CLI to PATH): `npm run pack:win`
  - macOS (DMG + PKG; PKG installs `/usr/local/bin/golem-provider`): `npm run pack:mac`
  - Linux (deb + AppImage; embeds CLI under app resources): `npm run pack:linux`

Notes:
- macOS: Use the PKG artifact to get the CLI symlink; DMG is drag-and-drop and won’t modify PATH.
- Windows: NSIS copies the CLI to `…/Golem Provider/bin` and puts that directory on PATH.
- Linux: The CLI binary is embedded under `Resources/cli/linux`. You can add a symlink to `/usr/local/bin` via a post-install step or surface an in-app “Install CLI” helper.

## Development / Run From Source

- Tooling: Poetry, Node (for GUIs), Make.
- Install all service dependencies: `make install`
- Run tests across services: `make test`
- Start all dev services (convenience): `make start`
- With discovery filters:
  - Testnet: `make start-testnet`
  - Mainnet: `make start-mainnet`

Notes:
- Use `.env`/`.env.dev` per service and `..._ENVIRONMENT` for dev ergonomics; discovery filters by `..._NETWORK` (`testnet|mainnet`).
- Avoid committing secrets; prefer environment variables for configuration.
