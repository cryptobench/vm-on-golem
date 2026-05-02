# VM on Golem Central Discovery Server

This package is the centralized discovery backend for VM on Golem. It is one backend for the broader discovery capability, not the whole discovery system.

For the full discovery architecture and backend selection rules, see [`../docs/discovery.md`](../docs/discovery.md).

## Role

Providers can publish resource advertisements to this FastAPI service, and requestors can query those advertisements over HTTP. The default production discovery backend is Arkiv; this server remains useful for legacy deployments, private/self-hosted networks, tests, and fallback environments.

## Installation

```bash
pip install golem-vm-central-discovery
```

The legacy package/command names are kept during the transition:

```bash
golem-central-discovery
golem-discovery
```

## Defaults

- Listen on `0.0.0.0:9001`.
- Store SQLite data at `~/.golem/central-discovery/central-discovery.db`.
- Rate limit to 100 requests per minute per IP.
- Remove expired advertisements every minute.
- Require provider refreshes every 5 minutes.

## Configuration

Canonical variables use `GOLEM_CENTRAL_DISCOVERY_*`. Legacy `GOLEM_DISCOVERY_*` variables are still accepted.

| Setting | Canonical Variable | Legacy Alias |
| --- | --- | --- |
| Host | `GOLEM_CENTRAL_DISCOVERY_HOST` | `GOLEM_DISCOVERY_HOST` |
| Port | `GOLEM_CENTRAL_DISCOVERY_PORT` | `GOLEM_DISCOVERY_PORT` |
| Debug | `GOLEM_CENTRAL_DISCOVERY_DEBUG` | `GOLEM_DISCOVERY_DEBUG` |
| Database URL | `GOLEM_CENTRAL_DISCOVERY_DATABASE_URL` | `GOLEM_DISCOVERY_DATABASE_URL` |
| Database Dir | `GOLEM_CENTRAL_DISCOVERY_DATABASE_DIR` | `GOLEM_DISCOVERY_DATABASE_DIR` |
| Database Name | `GOLEM_CENTRAL_DISCOVERY_DATABASE_NAME` | `GOLEM_DISCOVERY_DATABASE_NAME` |
| Rate Limit | `GOLEM_CENTRAL_DISCOVERY_RATE_LIMIT_PER_MINUTE` | `GOLEM_DISCOVERY_RATE_LIMIT_PER_MINUTE` |

## API

- `GET /health`
- `GET /api/v1/advertisements`
- `POST /api/v1/advertisements`
- `GET /api/v1/advertisements/{provider_id}`
- `DELETE /api/v1/advertisements/{provider_id}`

The HTTP API is intentionally unchanged by the rename.

## Development

```bash
poetry -C central-discovery-server install --with dev
poetry -C central-discovery-server run pytest
poetry -C central-discovery-server run golem-central-discovery
```
