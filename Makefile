.PHONY: install test start lock start-testnet start-mainnet

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
	GOLEM_PROVIDER_ENVIRONMENT=development poetry -C discovery-server run golem-discovery & \
	GOLEM_PROVIDER_ENVIRONMENT=development poetry -C provider-server run golem-provider start --network testnet & \
	GOLEM_REQUESTOR_ENVIRONMENT=development poetry -C requestor-server run golem server api --reload & \
	wait

start-testnet:
	@set -e; \
	GOLEM_PROVIDER_NETWORK=testnet GOLEM_PROVIDER_ENVIRONMENT=development poetry -C discovery-server run golem-discovery & \
	GOLEM_PROVIDER_NETWORK=testnet GOLEM_PROVIDER_ENVIRONMENT=development poetry -C provider-server run golem-provider start --network testnet & \
	GOLEM_REQUESTOR_NETWORK=testnet GOLEM_REQUESTOR_ENVIRONMENT=development poetry -C requestor-server run golem server api --reload & \
	wait

start-mainnet:
	@set -e; \
	GOLEM_PROVIDER_NETWORK=mainnet GOLEM_PROVIDER_ENVIRONMENT=production poetry -C discovery-server run golem-discovery & \
	GOLEM_PROVIDER_NETWORK=mainnet GOLEM_PROVIDER_ENVIRONMENT=production poetry -C provider-server run golem-provider start & \
	GOLEM_REQUESTOR_NETWORK=mainnet GOLEM_REQUESTOR_ENVIRONMENT=production poetry -C requestor-server run golem server api --reload & \
	wait
