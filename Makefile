.PHONY: install test start lock

install: lock
	poetry -C discovery-server install
	poetry -C provider-server install
	poetry -C requestor-server install

lock:
	poetry -C discovery-server lock
	poetry -C provider-server lock
	poetry -C requestor-server lock

test:
	# Ensure dev deps (e.g., requests for TestClient) are installed per service
	poetry -C discovery-server lock --no-update
	poetry -C discovery-server install --with dev --no-interaction
	poetry -C discovery-server run pytest discovery-server/tests || [ $$? -eq 5 ]
	poetry -C provider-server lock --no-update
	poetry -C provider-server install --with dev --no-interaction
	poetry -C provider-server run pytest provider-server/tests || [ $$? -eq 5 ]
	poetry -C requestor-server lock --no-update
	poetry -C requestor-server install --with dev --no-interaction
	poetry -C requestor-server run pytest requestor-server/tests || [ $$? -eq 5 ]

start:
	@set -e; \
	poetry -C discovery-server run golem-discovery & \
	poetry -C provider-server run dev & \
	poetry -C requestor-server run golem server api --reload & \
	wait
