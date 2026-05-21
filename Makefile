.PHONY: install test local prod start lock openapi api-generate api-check start-testnet start-mainnet dev-central-discovery dev-web start-dev

# --- Dev convenience variables (override via env when calling make) ---
# Ports
PROVIDER_API_PORT ?= 7466
# Central discovery websockets used in local development.
CENTRAL_DISCOVERY_PROVIDER_WS_URL ?= ws://127.0.0.1:9001/api/v1/discovery/providers
CENTRAL_DISCOVERY_REQUESTOR_WS_URL ?= ws://127.0.0.1:9001/api/v1/discovery/requestors
# Payments chain used by MetaMask/requestor-web.
L2_RPC_URL ?= https://rpc.hoodi.ethpandaops.io
L2_EXPLORER_URL ?= https://hoodi.etherscan.io
L2_CHAIN_ID_HEX ?= 0x88bb0
L2_CHAIN_NAME ?= Ethereum Hoodi
STREAM_PAYMENT_ADDRESS ?= $(shell python3 -c "import json; print(json.load(open('contracts/deployments/hoodi.json'))['StreamPayment']['address'])")
GLM_TOKEN_ADDRESS ?= $(shell python3 -c "import json; print(json.load(open('contracts/deployments/hoodi.json'))['StreamPayment'].get('glmToken') or '0x55555555555556AcFf9C332Ed151758858bd7a26')")

install: lock
	cd central-discovery-server && go mod download
	poetry -C provider-server install
	poetry -C shared-faucet install

lock:
	poetry -C provider-server lock

test:
	cd central-discovery-server && go test ./...
	poetry -C provider-server lock
	poetry -C provider-server install --with dev --no-interaction
	# Provider uses service-local pytest.ini to scope coverage sources
	poetry -C provider-server run pytest provider-server/tests --cov-fail-under=100 || [ $$? -eq 5 ]

local:
	python3 scripts/local_stack.py --mode local $(LOCAL_STACK_ARGS)

prod:
	python3 scripts/local_stack.py --mode prod $(LOCAL_STACK_ARGS)

openapi:
	poetry -C provider-server run python ../scripts/export_openapi.py provider ../openapi/provider.json

api-generate: openapi
	npm --prefix requestor-web run api:generate

api-check: api-generate
	git diff --exit-code -- openapi/provider.json requestor-web/lib/generated/api requestor-web/package.json requestor-web/package-lock.json requestor-web/orval.config.ts

start:
	@set -e; \
	# Start central discovery with bundled port checking
	(cd central-discovery-server && GOLEM_ENVIRONMENT=development GOLEM_CENTRAL_DISCOVERY_HOST=127.0.0.1 GOLEM_CENTRAL_DISCOVERY_PORT=9001 go run ./cmd/golem-central-discovery) & \
	# Start provider (development network, local IP)
	GOLEM_ENVIRONMENT=development \
	GOLEM_PROVIDER_NETWORK=development \
	GOLEM_PROVIDER_DISCOVERY_WS_URL=$(CENTRAL_DISCOVERY_PROVIDER_WS_URL) \
	poetry -C provider-server run golem-provider start & \
	# Start requestor web UI (development environment)
	GOLEM_ENVIRONMENT=development \
		NEXT_PUBLIC_GOLEM_ENVIRONMENT=development \
		NEXT_PUBLIC_DISCOVERY_WS_URL=$(CENTRAL_DISCOVERY_REQUESTOR_WS_URL) \
		NEXT_PUBLIC_STREAM_PAYMENT_ADDRESS=$(STREAM_PAYMENT_ADDRESS) \
	NEXT_PUBLIC_GLM_TOKEN_ADDRESS=$(GLM_TOKEN_ADDRESS) \
	NEXT_PUBLIC_EVM_CHAIN_ID=$(L2_CHAIN_ID_HEX) \
	NEXT_PUBLIC_EVM_CHAIN_NAME="$(L2_CHAIN_NAME)" \
	NEXT_PUBLIC_EVM_RPC_URL=$(L2_RPC_URL) \
	NEXT_PUBLIC_EVM_EXPLORER_URL=$(L2_EXPLORER_URL) \
	npm --prefix requestor-web run dev & \
	wait

start-testnet:
	@set -e; \
	(cd central-discovery-server && GOLEM_PROVIDER_NETWORK=testnet GOLEM_ENVIRONMENT=development go run ./cmd/golem-central-discovery) & \
	GOLEM_PROVIDER_NETWORK=testnet GOLEM_ENVIRONMENT=development GOLEM_PROVIDER_DISCOVERY_WS_URL=$(CENTRAL_DISCOVERY_PROVIDER_WS_URL) poetry -C provider-server run golem-provider start --network testnet & \
	wait

start-mainnet:
	@set -e; \
	(cd central-discovery-server && GOLEM_PROVIDER_NETWORK=mainnet GOLEM_ENVIRONMENT=production go run ./cmd/golem-central-discovery) & \
	GOLEM_PROVIDER_NETWORK=mainnet GOLEM_ENVIRONMENT=production GOLEM_PROVIDER_DISCOVERY_WS_URL=$(CENTRAL_DISCOVERY_PROVIDER_WS_URL) poetry -C provider-server run golem-provider start & \
	wait

# --- Dev helpers: Discovery + Web UI ---

dev-central-discovery:
	@set -e; \
	cd central-discovery-server && \
	GOLEM_ENVIRONMENT=development \
	GOLEM_CENTRAL_DISCOVERY_HOST=127.0.0.1 \
	GOLEM_CENTRAL_DISCOVERY_PORT=9001 \
	go run ./cmd/golem-central-discovery

dev-web:
	@set -e; \
	# Install deps (idempotent)
	npm --prefix requestor-web install >/dev/null; \
	# Run Next.js dev with discovery env configured
	GOLEM_ENVIRONMENT=development \
	NEXT_PUBLIC_GOLEM_ENVIRONMENT=development \
	NEXT_PUBLIC_DISCOVERY_WS_URL=$(CENTRAL_DISCOVERY_REQUESTOR_WS_URL) \
	NEXT_PUBLIC_STREAM_PAYMENT_ADDRESS=$(STREAM_PAYMENT_ADDRESS) \
	NEXT_PUBLIC_GLM_TOKEN_ADDRESS=$(GLM_TOKEN_ADDRESS) \
	NEXT_PUBLIC_EVM_CHAIN_ID=$(L2_CHAIN_ID_HEX) \
	NEXT_PUBLIC_EVM_CHAIN_NAME="$(L2_CHAIN_NAME)" \
	NEXT_PUBLIC_EVM_RPC_URL=$(L2_RPC_URL) \
	NEXT_PUBLIC_EVM_EXPLORER_URL=$(L2_EXPLORER_URL) \
	npm --prefix requestor-web run dev

# Start provider + central discovery + web UI (development network)
start-dev:
	@set -e; \
	# Ensure deps
	npm --prefix requestor-web install >/dev/null; \
	# Start central discovery with bundled port checking
	(cd central-discovery-server && GOLEM_ENVIRONMENT=development GOLEM_CENTRAL_DISCOVERY_HOST=127.0.0.1 GOLEM_CENTRAL_DISCOVERY_PORT=9001 go run ./cmd/golem-central-discovery) & \
	# Start provider (development network, local IP)
	GOLEM_ENVIRONMENT=development \
	GOLEM_PROVIDER_NETWORK=development \
	GOLEM_PROVIDER_DISCOVERY_WS_URL=$(CENTRAL_DISCOVERY_PROVIDER_WS_URL) \
	poetry -C provider-server run golem-provider start & \
	# Start web UI (development environment)
	GOLEM_ENVIRONMENT=development \
	NEXT_PUBLIC_GOLEM_ENVIRONMENT=development \
	NEXT_PUBLIC_DISCOVERY_WS_URL=$(CENTRAL_DISCOVERY_REQUESTOR_WS_URL) \
	NEXT_PUBLIC_STREAM_PAYMENT_ADDRESS=$(STREAM_PAYMENT_ADDRESS) \
	NEXT_PUBLIC_GLM_TOKEN_ADDRESS=$(GLM_TOKEN_ADDRESS) \
	NEXT_PUBLIC_EVM_CHAIN_ID=$(L2_CHAIN_ID_HEX) \
	NEXT_PUBLIC_EVM_CHAIN_NAME="$(L2_CHAIN_NAME)" \
	NEXT_PUBLIC_EVM_RPC_URL=$(L2_RPC_URL) \
	NEXT_PUBLIC_EVM_EXPLORER_URL=$(L2_EXPLORER_URL) \
	npm --prefix requestor-web run dev & \
	wait

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
