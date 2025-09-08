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
	poetry -C discovery-server run pytest || [ $$? -eq 5 ]
	poetry -C provider-server run pytest || [ $$? -eq 5 ]
	poetry -C requestor-server run pytest || [ $$? -eq 5 ]

start:
	@set -e; \
	poetry -C discovery-server run golem-discovery & \
	poetry -C provider-server run dev & \
	poetry -C requestor-server run golem server api --reload & \
	wait
