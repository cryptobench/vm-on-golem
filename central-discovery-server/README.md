# VM on Golem Central Discovery

Central discovery is a Go websocket service with an in-memory live provider
registry. Providers publish advertisements over
`WS /api/v1/discovery/providers`; requestors browse through
`WS /api/v1/discovery/requestors`. A provider is discoverable only while its
websocket is connected.

## Install

```bash
go install ./cmd/golem-central-discovery
```

Release builds are published as `golem-central-discovery-<os>-<arch>.tar.gz`
assets on GitHub releases tagged `central-discovery-v*`.

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
cd central-discovery-server
go test ./...
go run ./cmd/golem-central-discovery
```

To update an installed release binary in place:

```bash
scripts/update_central_discovery.sh /usr/local/bin/golem-central-discovery
```
