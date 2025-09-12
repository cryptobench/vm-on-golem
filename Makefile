.PHONY: install test start lock start-testnet start-mainnet dev-proxy dev-web dev-proxy-web start-dev

# --- Dev convenience variables (override via env when calling make) ---
# Ports
PORT_CHECKER_PORT ?= 9000
# Shared token between UI and proxy (public in UI; use dev-only value)
PORT_CHECKER_TOKEN ?= dev-token
# Golem Base RPC/WS for provider resolution (L3 EthWarsaw Holesky)
GOLEM_BASE_RPC_URL ?= https://ethwarsaw.holesky.golemdb.io/rpc
GOLEM_BASE_WS_URL ?= wss://ethwarsaw.holesky.golemdb.io/rpc/ws
# Optional dev-only endpoints for Golem Base
GOLEM_BASE_DEV_RPC_URL ?=
GOLEM_BASE_DEV_WS_URL ?=
 # Discovery API used by the proxy to resolve provider IPs (central discovery). For local-only setups,
 # point this to any reachable discovery instance. Default to public demo endpoint.
DISCOVERY_API_URL ?= http://195.201.39.101:9001/api/v1

install: lock
	poetry -C discovery-server install
	poetry -C provider-server install
	poetry -C requestor-server install
	poetry -C shared-faucet install

lock:
	poetry -C discovery-server lock
	poetry -C provider-server lock
	poetry -C requestor-server lock

test:
	# Ensure dev deps (e.g., requests for TestClient) are installed per service
	poetry -C discovery-server lock --no-update
	poetry -C discovery-server install --with dev --no-interaction
	poetry -C discovery-server run pytest discovery-server/tests --cov=discovery --cov-report=term-missing --cov-fail-under=100 || [ $$? -eq 5 ]
	poetry -C provider-server lock --no-update
	poetry -C provider-server install --with dev --no-interaction
	# Provider uses service-local pytest.ini to scope coverage sources
	poetry -C provider-server run pytest provider-server/tests --cov-fail-under=100 || [ $$? -eq 5 ]
	poetry -C requestor-server lock --no-update
	poetry -C requestor-server install --with dev --no-interaction
	# Requestor uses service-local pytest.ini to scope coverage sources
	poetry -C requestor-server run pytest requestor-server/tests || [ $$? -eq 5 ]

start:
	@set -e; \
	# Start provider (development network, local IP)
	GOLEM_ENVIRONMENT=development \
	GOLEM_PROVIDER_NETWORK=development \
	poetry -C provider-server run golem-provider start & \
	# Start port-checker (proxy) pointing at configured discovery (public demo API by default)
	GOLEM_ENVIRONMENT=development \
	PORT_CHECKER_HOST=127.0.0.1 \
	PORT_CHECKER_PORT=$(PORT_CHECKER_PORT) \
	PORT_CHECKER_PROXY_TOKEN=$(PORT_CHECKER_TOKEN) \
	DISCOVERY_API_URL=$(DISCOVERY_API_URL) \
	GOLEM_BASE_RPC_URL=$(if $(GOLEM_BASE_DEV_RPC_URL),$(GOLEM_BASE_DEV_RPC_URL),$(GOLEM_BASE_RPC_URL)) \
	GOLEM_BASE_WS_URL=$(if $(GOLEM_BASE_DEV_WS_URL),$(GOLEM_BASE_DEV_WS_URL),$(GOLEM_BASE_WS_URL)) \
	poetry -C port-checker-server run port-checker & \
	# Start requestor web UI (development environment)
	GOLEM_ENVIRONMENT=development \
	NEXT_PUBLIC_GOLEM_ENVIRONMENT=development \
	NEXT_PUBLIC_DISCOVERY_API_URL=$(DISCOVERY_API_URL) \
	NEXT_PUBLIC_PORT_CHECKER_URL=http://127.0.0.1:$(PORT_CHECKER_PORT) \
	NEXT_PUBLIC_PORT_CHECKER_TOKEN=$(PORT_CHECKER_TOKEN) \
	NEXT_PUBLIC_GOLEM_BASE_DEV_RPC_URL=$(GOLEM_BASE_DEV_RPC_URL) \
	NEXT_PUBLIC_GOLEM_BASE_DEV_WS_URL=$(GOLEM_BASE_DEV_WS_URL) \
	npm --prefix requestor-web run dev & \
	wait

start-testnet:
	@set -e; \
	GOLEM_PROVIDER_NETWORK=testnet GOLEM_ENVIRONMENT=development poetry -C discovery-server run golem-discovery & \
	GOLEM_PROVIDER_NETWORK=testnet GOLEM_ENVIRONMENT=development poetry -C provider-server run golem-provider start --network testnet & \
	GOLEM_REQUESTOR_NETWORK=testnet GOLEM_ENVIRONMENT=development poetry -C requestor-server run golem server api --reload & \
	wait

start-mainnet:
	@set -e; \
	GOLEM_PROVIDER_NETWORK=mainnet GOLEM_ENVIRONMENT=production poetry -C discovery-server run golem-discovery & \
	GOLEM_PROVIDER_NETWORK=mainnet GOLEM_ENVIRONMENT=production poetry -C provider-server run golem-provider start & \
	GOLEM_REQUESTOR_NETWORK=mainnet GOLEM_ENVIRONMENT=production poetry -C requestor-server run golem server api --reload & \
	wait

# --- Dev helpers: Port-checker proxy + Discovery + Web UI ---

dev-proxy:
	@set -e; \
	# Install deps (idempotent)
	poetry -C port-checker-server install >/dev/null; \
	# Start port-checker (proxy enabled) pointing at configured discovery
	GOLEM_ENVIRONMENT=development \
	PORT_CHECKER_HOST=127.0.0.1 \
	PORT_CHECKER_PORT=$(PORT_CHECKER_PORT) \
	PORT_CHECKER_PROXY_TOKEN=$(PORT_CHECKER_TOKEN) \
	DISCOVERY_API_URL=$(DISCOVERY_API_URL) \
	GOLEM_BASE_RPC_URL=$(if $(GOLEM_BASE_DEV_RPC_URL),$(GOLEM_BASE_DEV_RPC_URL),$(GOLEM_BASE_RPC_URL)) \
	GOLEM_BASE_WS_URL=$(if $(GOLEM_BASE_DEV_WS_URL),$(GOLEM_BASE_DEV_WS_URL),$(GOLEM_BASE_WS_URL)) \
	poetry -C port-checker-server run port-checker

dev-web:
	@set -e; \
	# Install deps (idempotent)
	npm --prefix requestor-web install >/dev/null; \
	# Run Next.js dev with proxy + discovery env configured
	GOLEM_ENVIRONMENT=development \
	NEXT_PUBLIC_GOLEM_ENVIRONMENT=development \
	NEXT_PUBLIC_DISCOVERY_API_URL=$(DISCOVERY_API_URL) \
	NEXT_PUBLIC_PORT_CHECKER_URL=http://127.0.0.1:$(PORT_CHECKER_PORT) \
	NEXT_PUBLIC_PORT_CHECKER_TOKEN=$(PORT_CHECKER_TOKEN) \
	NEXT_PUBLIC_GOLEM_BASE_DEV_RPC_URL=$(GOLEM_BASE_DEV_RPC_URL) \
	NEXT_PUBLIC_GOLEM_BASE_DEV_WS_URL=$(GOLEM_BASE_DEV_WS_URL) \
	npm --prefix requestor-web run dev

dev-proxy-web:
	@set -e; \
	# Install deps
	poetry -C port-checker-server install >/dev/null; \
	npm --prefix requestor-web install >/dev/null; \
	# Start port-checker (proxy)
	GOLEM_ENVIRONMENT=development \
	PORT_CHECKER_HOST=127.0.0.1 \
	PORT_CHECKER_PORT=$(PORT_CHECKER_PORT) \
	PORT_CHECKER_PROXY_TOKEN=$(PORT_CHECKER_TOKEN) \
	DISCOVERY_API_URL=$(DISCOVERY_API_URL) \
	GOLEM_BASE_RPC_URL=$(if $(GOLEM_BASE_DEV_RPC_URL),$(GOLEM_BASE_DEV_RPC_URL),$(GOLEM_BASE_RPC_URL)) \
	GOLEM_BASE_WS_URL=$(if $(GOLEM_BASE_DEV_WS_URL),$(GOLEM_BASE_DEV_WS_URL),$(GOLEM_BASE_WS_URL)) \
	poetry -C port-checker-server run port-checker & \
	# Start web UI
	GOLEM_ENVIRONMENT=development \
	NEXT_PUBLIC_GOLEM_ENVIRONMENT=development \
	NEXT_PUBLIC_DISCOVERY_API_URL=$(DISCOVERY_API_URL) \
	NEXT_PUBLIC_PORT_CHECKER_URL=http://127.0.0.1:$(PORT_CHECKER_PORT) \
	NEXT_PUBLIC_PORT_CHECKER_TOKEN=$(PORT_CHECKER_TOKEN) \
	NEXT_PUBLIC_GOLEM_BASE_DEV_RPC_URL=$(GOLEM_BASE_DEV_RPC_URL) \
	NEXT_PUBLIC_GOLEM_BASE_DEV_WS_URL=$(GOLEM_BASE_DEV_WS_URL) \
	npm --prefix requestor-web run dev & \
	wait

# Start provider + dev proxy + web UI (development network)
start-dev:
	@set -e; \
	# Ensure deps
	poetry -C port-checker-server install >/dev/null; \
	npm --prefix requestor-web install >/dev/null; \
	# Start provider (development network, local IP)
	GOLEM_ENVIRONMENT=development \
	GOLEM_PROVIDER_NETWORK=development \
	poetry -C provider-server run golem-provider start & \
	# Start port-checker (dev endpoints if provided)
	GOLEM_ENVIRONMENT=development \
	PORT_CHECKER_HOST=127.0.0.1 \
	PORT_CHECKER_PORT=$(PORT_CHECKER_PORT) \
	PORT_CHECKER_PROXY_TOKEN=$(PORT_CHECKER_TOKEN) \
	DISCOVERY_API_URL=$(DISCOVERY_API_URL) \
	GOLEM_BASE_RPC_URL=$(if $(GOLEM_BASE_DEV_RPC_URL),$(GOLEM_BASE_DEV_RPC_URL),$(GOLEM_BASE_RPC_URL)) \
	GOLEM_BASE_WS_URL=$(if $(GOLEM_BASE_DEV_WS_URL),$(GOLEM_BASE_DEV_WS_URL),$(GOLEM_BASE_WS_URL)) \
	poetry -C port-checker-server run port-checker & \
	# Start web UI (development environment)
	GOLEM_ENVIRONMENT=development \
	NEXT_PUBLIC_GOLEM_ENVIRONMENT=development \
	NEXT_PUBLIC_DISCOVERY_API_URL=$(DISCOVERY_API_URL) \
	NEXT_PUBLIC_PORT_CHECKER_URL=http://127.0.0.1:$(PORT_CHECKER_PORT) \
	NEXT_PUBLIC_PORT_CHECKER_TOKEN=$(PORT_CHECKER_TOKEN) \
	NEXT_PUBLIC_GOLEM_BASE_DEV_RPC_URL=$(GOLEM_BASE_DEV_RPC_URL) \
	NEXT_PUBLIC_GOLEM_BASE_DEV_WS_URL=$(GOLEM_BASE_DEV_WS_URL) \
	npm --prefix requestor-web run dev & \
	wait

# Alias for convenience
.PHONY: devwebproxy
devwebproxy: dev-proxy-web
