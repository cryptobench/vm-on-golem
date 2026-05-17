# VM on Golem Central Discovery

Central discovery is a websocket-only live provider registry. Providers publish
advertisements over `WS /api/v1/discovery/providers`; requestors browse through
`WS /api/v1/discovery/requestors`. A provider is discoverable only while its
websocket is connected.

## Install

```bash
pip install golem-vm-central-discovery
```

## Run

```bash
golem-central-discovery
```

## Configuration

Only `GOLEM_CENTRAL_DISCOVERY_*` variables are accepted.

| Setting | Variable | Default |
| --- | --- | --- |
| Host | `GOLEM_CENTRAL_DISCOVERY_HOST` | `0.0.0.0` |
| Port | `GOLEM_CENTRAL_DISCOVERY_PORT` | `9001` |
| Debug | `GOLEM_CENTRAL_DISCOVERY_DEBUG` | `false` |
| Rate limit | `GOLEM_CENTRAL_DISCOVERY_RATE_LIMIT_PER_MINUTE` | `100` |

## Endpoints

- `GET /health`
- `WS /api/v1/discovery/providers`
- `WS /api/v1/discovery/requestors`

There are no HTTP advertisement endpoints and no persisted advertisement store.

## Development

```bash
poetry -C central-discovery-server install --with dev
poetry -C central-discovery-server run pytest
poetry -C central-discovery-server run golem-central-discovery
```
