.PHONY: install test local start lock openapi api-generate api-check start-testnet start-mainnet dev-proxy dev-web dev-proxy-web start-dev

# --- Dev convenience variables (override via env when calling make) ---
# Ports
PORT_CHECKER_PORT ?= 9000
# Shared token between UI and proxy (public in UI; use dev-only value)
PORT_CHECKER_TOKEN ?= dev-token
# Arkiv RPC/WS for provider resolution (Kaolin Hoodi).
ARKIV_RPC_URL ?= https://kaolin.hoodi.arkiv.network/rpc
ARKIV_WS_URL ?= wss://kaolin.hoodi.arkiv.network/rpc/ws
# Optional dev-only Arkiv endpoints.
ARKIV_DEV_RPC_URL ?=
ARKIV_DEV_WS_URL ?=
# Central discovery API used by the proxy. For local-only setups, point this to
# any reachable central discovery instance. Default to public demo endpoint.
CENTRAL_DISCOVERY_API_URL ?= http://195.201.39.101:9001/api/v1
# Payments chain used by MetaMask/requestor-web.
L2_RPC_URL ?= https://l2.hoodi.arkiv.network/rpc
L2_EXPLORER_URL ?= https://explorer.l2.hoodi.arkiv.network
L2_CHAIN_ID_HEX ?= 0x6013a
L2_CHAIN_NAME ?= Arkiv L2 Hoodi
STREAM_PAYMENT_ADDRESS ?= $(shell python3 -c "import json; print(json.load(open('contracts/deployments/l2.json'))['StreamPayment']['address'])")
GLM_TOKEN_ADDRESS ?= $(shell python3 -c "import json; print(json.load(open('contracts/deployments/l2.json'))['StreamPayment'].get('glmToken') or '0x0000000000000000000000000000000000000000')")

install: lock
	poetry -C central-discovery-server install
	poetry -C port-checker-server install
	poetry -C provider-server install
	poetry -C requestor-server install
	poetry -C shared-faucet install

lock:
	poetry -C central-discovery-server lock
	poetry -C port-checker-server lock
	poetry -C provider-server lock
	poetry -C requestor-server lock

test:
	# Ensure dev deps (e.g., requests for TestClient) are installed per service
	poetry -C central-discovery-server lock
	poetry -C central-discovery-server install --with dev --no-interaction
	poetry -C central-discovery-server run pytest central-discovery-server/tests --cov=central_discovery --cov-report=term-missing --cov-fail-under=100 || [ $$? -eq 5 ]
	poetry -C port-checker-server lock
	poetry -C port-checker-server install --with dev --no-interaction
	poetry -C port-checker-server run pytest port-checker-server/tests || [ $$? -eq 5 ]
	poetry -C provider-server lock
	poetry -C provider-server install --with dev --no-interaction
	# Provider uses service-local pytest.ini to scope coverage sources
	poetry -C provider-server run pytest provider-server/tests --cov-fail-under=100 || [ $$? -eq 5 ]
	poetry -C requestor-server lock
	poetry -C requestor-server install --with dev --no-interaction
	# Requestor uses service-local pytest.ini to scope coverage sources
	poetry -C requestor-server run pytest requestor-server/tests || [ $$? -eq 5 ]

local:
	python3 scripts/local_stack.py $(LOCAL_STACK_ARGS)

openapi:
	poetry -C central-discovery-server run python ../scripts/export_openapi.py central-discovery ../openapi/central-discovery.json
	poetry -C port-checker-server run python ../scripts/export_openapi.py port-checker ../openapi/port-checker.json
	poetry -C provider-server run python ../scripts/export_openapi.py provider ../openapi/provider.json
	poetry -C requestor-server run python ../scripts/export_openapi.py requestor ../openapi/requestor.json

api-generate: openapi
	npm --prefix requestor-web run api:generate

api-check: api-generate
	git diff --exit-code -- openapi requestor-web/lib/generated/api requestor-web/package.json requestor-web/package-lock.json requestor-web/orval.config.ts

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
	CENTRAL_DISCOVERY_API_URL=$(CENTRAL_DISCOVERY_API_URL) \
	ARKIV_RPC_URL=$(if $(ARKIV_DEV_RPC_URL),$(ARKIV_DEV_RPC_URL),$(ARKIV_RPC_URL)) \
	ARKIV_WS_URL=$(if $(ARKIV_DEV_WS_URL),$(ARKIV_DEV_WS_URL),$(ARKIV_WS_URL)) \
	poetry -C port-checker-server run port-checker & \
	# Start requestor web UI (development environment)
	GOLEM_ENVIRONMENT=development \
	NEXT_PUBLIC_GOLEM_ENVIRONMENT=development \
	NEXT_PUBLIC_DISCOVERY_API_URL=$(CENTRAL_DISCOVERY_API_URL) \
	NEXT_PUBLIC_PORT_CHECKER_URL=http://127.0.0.1:$(PORT_CHECKER_PORT) \
	NEXT_PUBLIC_PORT_CHECKER_TOKEN=$(PORT_CHECKER_TOKEN) \
	NEXT_PUBLIC_STREAM_PAYMENT_ADDRESS=$(STREAM_PAYMENT_ADDRESS) \
	NEXT_PUBLIC_GLM_TOKEN_ADDRESS=$(GLM_TOKEN_ADDRESS) \
	NEXT_PUBLIC_EVM_CHAIN_ID=$(L2_CHAIN_ID_HEX) \
	NEXT_PUBLIC_EVM_CHAIN_NAME="$(L2_CHAIN_NAME)" \
	NEXT_PUBLIC_EVM_RPC_URL=$(L2_RPC_URL) \
	NEXT_PUBLIC_EVM_EXPLORER_URL=$(L2_EXPLORER_URL) \
	NEXT_PUBLIC_ARKIV_DEV_RPC_URL=$(ARKIV_DEV_RPC_URL) \
	NEXT_PUBLIC_ARKIV_DEV_WS_URL=$(ARKIV_DEV_WS_URL) \
	npm --prefix requestor-web run dev & \
	wait

start-testnet:
	@set -e; \
	GOLEM_PROVIDER_NETWORK=testnet GOLEM_ENVIRONMENT=development poetry -C central-discovery-server run golem-central-discovery & \
	GOLEM_PROVIDER_NETWORK=testnet GOLEM_ENVIRONMENT=development poetry -C provider-server run golem-provider start --network testnet & \
	GOLEM_REQUESTOR_NETWORK=testnet GOLEM_ENVIRONMENT=development poetry -C requestor-server run golem server api --reload & \
	wait

start-mainnet:
	@set -e; \
	GOLEM_PROVIDER_NETWORK=mainnet GOLEM_ENVIRONMENT=production poetry -C central-discovery-server run golem-central-discovery & \
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
	CENTRAL_DISCOVERY_API_URL=$(CENTRAL_DISCOVERY_API_URL) \
	ARKIV_RPC_URL=$(if $(ARKIV_DEV_RPC_URL),$(ARKIV_DEV_RPC_URL),$(ARKIV_RPC_URL)) \
	ARKIV_WS_URL=$(if $(ARKIV_DEV_WS_URL),$(ARKIV_DEV_WS_URL),$(ARKIV_WS_URL)) \
	poetry -C port-checker-server run port-checker

dev-web:
	@set -e; \
	# Install deps (idempotent)
	npm --prefix requestor-web install >/dev/null; \
	# Run Next.js dev with proxy + discovery env configured
	GOLEM_ENVIRONMENT=development \
	NEXT_PUBLIC_GOLEM_ENVIRONMENT=development \
	NEXT_PUBLIC_DISCOVERY_API_URL=$(CENTRAL_DISCOVERY_API_URL) \
	NEXT_PUBLIC_PORT_CHECKER_URL=http://127.0.0.1:$(PORT_CHECKER_PORT) \
	NEXT_PUBLIC_PORT_CHECKER_TOKEN=$(PORT_CHECKER_TOKEN) \
	NEXT_PUBLIC_STREAM_PAYMENT_ADDRESS=$(STREAM_PAYMENT_ADDRESS) \
	NEXT_PUBLIC_GLM_TOKEN_ADDRESS=$(GLM_TOKEN_ADDRESS) \
	NEXT_PUBLIC_EVM_CHAIN_ID=$(L2_CHAIN_ID_HEX) \
	NEXT_PUBLIC_EVM_CHAIN_NAME="$(L2_CHAIN_NAME)" \
	NEXT_PUBLIC_EVM_RPC_URL=$(L2_RPC_URL) \
	NEXT_PUBLIC_EVM_EXPLORER_URL=$(L2_EXPLORER_URL) \
	NEXT_PUBLIC_ARKIV_DEV_RPC_URL=$(ARKIV_DEV_RPC_URL) \
	NEXT_PUBLIC_ARKIV_DEV_WS_URL=$(ARKIV_DEV_WS_URL) \
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
	CENTRAL_DISCOVERY_API_URL=$(CENTRAL_DISCOVERY_API_URL) \
	ARKIV_RPC_URL=$(if $(ARKIV_DEV_RPC_URL),$(ARKIV_DEV_RPC_URL),$(ARKIV_RPC_URL)) \
	ARKIV_WS_URL=$(if $(ARKIV_DEV_WS_URL),$(ARKIV_DEV_WS_URL),$(ARKIV_WS_URL)) \
	poetry -C port-checker-server run port-checker & \
	# Start web UI
	GOLEM_ENVIRONMENT=development \
	NEXT_PUBLIC_GOLEM_ENVIRONMENT=development \
	NEXT_PUBLIC_DISCOVERY_API_URL=$(CENTRAL_DISCOVERY_API_URL) \
	NEXT_PUBLIC_PORT_CHECKER_URL=http://127.0.0.1:$(PORT_CHECKER_PORT) \
	NEXT_PUBLIC_PORT_CHECKER_TOKEN=$(PORT_CHECKER_TOKEN) \
	NEXT_PUBLIC_STREAM_PAYMENT_ADDRESS=$(STREAM_PAYMENT_ADDRESS) \
	NEXT_PUBLIC_GLM_TOKEN_ADDRESS=$(GLM_TOKEN_ADDRESS) \
	NEXT_PUBLIC_EVM_CHAIN_ID=$(L2_CHAIN_ID_HEX) \
	NEXT_PUBLIC_EVM_CHAIN_NAME="$(L2_CHAIN_NAME)" \
	NEXT_PUBLIC_EVM_RPC_URL=$(L2_RPC_URL) \
	NEXT_PUBLIC_EVM_EXPLORER_URL=$(L2_EXPLORER_URL) \
	NEXT_PUBLIC_ARKIV_DEV_RPC_URL=$(ARKIV_DEV_RPC_URL) \
	NEXT_PUBLIC_ARKIV_DEV_WS_URL=$(ARKIV_DEV_WS_URL) \
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
	CENTRAL_DISCOVERY_API_URL=$(CENTRAL_DISCOVERY_API_URL) \
	ARKIV_RPC_URL=$(if $(ARKIV_DEV_RPC_URL),$(ARKIV_DEV_RPC_URL),$(ARKIV_RPC_URL)) \
	ARKIV_WS_URL=$(if $(ARKIV_DEV_WS_URL),$(ARKIV_DEV_WS_URL),$(ARKIV_WS_URL)) \
	poetry -C port-checker-server run port-checker & \
	# Start web UI (development environment)
	GOLEM_ENVIRONMENT=development \
	NEXT_PUBLIC_GOLEM_ENVIRONMENT=development \
	NEXT_PUBLIC_DISCOVERY_API_URL=$(CENTRAL_DISCOVERY_API_URL) \
	NEXT_PUBLIC_PORT_CHECKER_URL=http://127.0.0.1:$(PORT_CHECKER_PORT) \
	NEXT_PUBLIC_PORT_CHECKER_TOKEN=$(PORT_CHECKER_TOKEN) \
	NEXT_PUBLIC_STREAM_PAYMENT_ADDRESS=$(STREAM_PAYMENT_ADDRESS) \
	NEXT_PUBLIC_GLM_TOKEN_ADDRESS=$(GLM_TOKEN_ADDRESS) \
	NEXT_PUBLIC_EVM_CHAIN_ID=$(L2_CHAIN_ID_HEX) \
	NEXT_PUBLIC_EVM_CHAIN_NAME="$(L2_CHAIN_NAME)" \
	NEXT_PUBLIC_EVM_RPC_URL=$(L2_RPC_URL) \
	NEXT_PUBLIC_EVM_EXPLORER_URL=$(L2_EXPLORER_URL) \
	NEXT_PUBLIC_ARKIV_DEV_RPC_URL=$(ARKIV_DEV_RPC_URL) \
	NEXT_PUBLIC_ARKIV_DEV_WS_URL=$(ARKIV_DEV_WS_URL) \
	npm --prefix requestor-web run dev & \
	wait

# Alias for convenience
.PHONY: devwebproxy
devwebproxy: dev-proxy-web

# --- Faucet helpers ---

.PHONY: faucet-batch
faucet-batch:
	@set -e; \
	if [ -z "$$FUND_ADDR" ]; then \
	  echo "Usage: make faucet-batch FUND_ADDR=0xYourAddress [COUNT=20]"; \
	  exit 2; \
	fi; \
	# Ensure the shared-faucet environment is installed (idempotent)
	poetry -C shared-faucet install >/dev/null; \
	# Run faucet N times using the shared PoW faucet client
	cd shared-faucet; \
	COUNT=$${COUNT:-20} \
	FUND_ADDR="$$FUND_ADDR" \
	poetry run python ../scripts/faucet_batch.py
