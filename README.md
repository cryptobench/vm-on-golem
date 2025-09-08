# VM-on-Golem

This project provides a framework for running virtual machines on the Golem Network.

## Streaming Payments via GLM (Polygon)

This repo includes an on‑chain streaming payment integration using a minimal EIP‑1620‑style contract:

- Contracts in `contracts/` (Hardhat). Deploy to Polygon PoS.
- Provider API gates VM creation on a valid funded stream addressed to the provider.
- Requestor can top up deposit to extend runtime; provider can withdraw vested funds.
- Optional background monitor on provider can stop VMs when remaining runway < threshold and withdraw periodically (gas‑aware).

Quick links:

- Deploy/contract docs: `contracts/README.md`
- Provider configuration and API: `provider-server/README.md`
- Requestor usage and flow: `requestor-server/README.md`

## Environment Configuration

The applications within this repository (provider-server, requestor-server) can be configured to run in different environments, such as `production` or `development`. This is controlled via environment variables.

### Provider Server

To run the provider server in development mode, set the `GOLEM_PROVIDER_ENVIRONMENT` environment variable:

```bash
export GOLEM_PROVIDER_ENVIRONMENT="development"
# Now run your provider application
```

### Requestor Server

To run the requestor server in development mode, set the `GOLEM_REQUESTOR_ENVIRONMENT` environment variable:

```bash
export GOLEM_REQUESTOR_ENVIRONMENT="development"
# Now run your requestor application
```

If these variables are not set, the applications will default to `production` mode.

## Development

This repository provides a Makefile to streamline common tasks during development.

### Install dependencies

Install the discovery, provider, and requestor packages using Poetry:

```bash
make install
```

### Run tests

Execute unit tests for all packages:

```bash
make test
```

### Start development servers

Launch the discovery, provider, and requestor servers concurrently:

```bash
make start
```

This runs all three services in the foreground for local development.
