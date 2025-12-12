# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

VM on Golem is a decentralized VM rental platform. Requestors can rent VMs from providers using GLM tokens with streaming payments on Ethereum L2 (Hoodi/Kaolin).

## Build & Development Commands

```bash
# Install all Poetry dependencies
make install

# Run all tests with coverage (discovery, provider, requestor)
make test

# Start full development stack (provider + port-checker proxy + requestor web)
make start

# Start only proxy + web UI (useful for frontend work)
make dev-proxy-web
```

### Per-Service Commands

```bash
# Provider server
poetry -C provider-server run golem-provider start
poetry -C provider-server run pytest provider-server/tests

# Requestor server
poetry -C requestor-server run golem server api --reload
poetry -C requestor-server run pytest requestor-server/tests

# Port checker proxy
poetry -C port-checker-server run port-checker

# Web UI (Next.js)
npm --prefix requestor-web run dev
npm --prefix requestor-web run lint

# Smart contracts (Hardhat)
cd contracts && npm run build

# Discovery server (DEPRECATED - legacy only)
poetry -C discovery-server run golem-discovery
poetry -C discovery-server run pytest discovery-server/tests
```

### Linting & Formatting

```bash
poetry -C <service> run black .
poetry -C <service> run isort .
poetry -C <service> run pylint <package>
poetry -C <service> run mypy <package>
```

## Architecture

### Provider Discovery (Golem Base)

Provider discovery uses **Golem Base**, a decentralized on-chain registry on the Kaolin L3 chain. Providers advertise resources as on-chain entities with annotations; requestors query using `golem-base-sdk`.

Key discovery files:
- `provider-server/provider/discovery/golem_base_advertiser.py` - `GolemBaseAdvertiser` posts/updates provider ads on-chain
- `requestor-server/requestor/services/provider_service.py` - `ProviderService._find_providers_golem_base()` queries providers

Annotations stored on-chain: `golem_type`, `golem_provider_id`, `golem_ip_address`, `golem_cpu`, `golem_memory`, `golem_storage`, pricing fields, etc.

### Core Services (Python/Poetry)

| Service | Package | Entry Point | Python |
|---------|---------|-------------|--------|
| provider-server | `provider` | `golem-provider` | 3.11 |
| requestor-server | `requestor` | `golem` | 3.11 |
| port-checker-server | `port_checker` | `port-checker` | 3.10+ |
| discovery-server | `discovery` | `golem-discovery` | 3.9 | ⚠️ DEPRECATED |

- **provider-server**: Runs on provider machines. Manages VMs (libvirt/QEMU), advertises to Golem Base, handles payments via streaming contracts.
- **requestor-server**: CLI (`golem vm ...`) for finding providers, creating/managing VMs, and SSH connections.
- **port-checker-server**: FastAPI proxy service for connectivity checks and provider resolution.
- **discovery-server**: ⚠️ **DEPRECATED** - Old centralized FastAPI discovery service. Replaced by decentralized Golem Base. Kept for legacy/fallback only.

### Web & GUI

- **requestor-web**: Next.js 14 + Tailwind + Tremor UI. Browser-based requestor interface with wallet integration.
- **requestor-gui/provider-gui**: Electron shells (development).

### Shared Packages

- **streaming-abi**: Python package with `STREAM_PAYMENT_ABI` and `ERC20_ABI` for blockchain interactions.
- **shared-faucet**: Testnet faucet client (`golem-faucet`).
- **golem-base-sdk**: External SDK for Golem Base (L3) chain interactions.

### Smart Contracts

- **contracts/**: Hardhat project with StreamPayment Solidity contracts. Deployed to Polygon, Kaolin (L3), and L2 Hoodi.

## Payment Flow

Streaming payments use an on-chain StreamPayment contract:
1. Requestor creates a stream with `createStream` (payable for native ETH or requires `approve` for ERC20)
2. Provider monitors stream and calls `withdraw` periodically
3. Either party can `terminate`; requestor can `topUp`

Key files for payment logic:
- `requestor-server/requestor/payments/blockchain_service.py`
- `provider-server/provider/payments/blockchain_service.py`
- `streaming-abi/golem_streaming_abi/__init__.py`

## Environment Variables

Development uses `GOLEM_ENVIRONMENT=development`. Key variables:
- `GOLEM_BASE_RPC_URL` / `GOLEM_BASE_WS_URL`: L3 Kaolin RPC endpoints
- `DISCOVERY_API_URL`: Discovery service endpoint
- `PORT_CHECKER_PORT`, `PORT_CHECKER_TOKEN`: Proxy configuration

## Code Style

- Python: Black (88 cols), isort (profile=black), type hints on new code
- Web: ESLint + Next.js conventions, Tailwind CSS
- Commits: imperative mood, scoped prefix when helpful (e.g., `provider: fix config reload`)

## Testing

- Framework: pytest + pytest-asyncio + pytest-cov
- Location: `<service>/tests/test_*.py`
- Coverage requirement: 100% for discovery and provider services
- Prefer unit tests with mocked I/O; avoid real network/chain access

## ABI Changes Checklist

When modifying StreamPayment contract interface:
1. Update `streaming-abi/golem_streaming_abi/__init__.py`
2. Update blockchain services in both provider and requestor
3. Run `make test` to verify guard tests pass
4. Refresh locks: `make install`
