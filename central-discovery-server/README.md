# VM on Golem Central Discovery

Central discovery is a Go service with an in-memory live provider registry and
bundled provider port verification. Providers publish advertisements over
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
| Port check retries | `GOLEM_CENTRAL_DISCOVERY_PORT_CHECK_RETRIES` | `1` |
| Port check retry delay | `GOLEM_CENTRAL_DISCOVERY_PORT_CHECK_RETRY_DELAY_SECONDS` | `0.25` |
| Port check timeout | `GOLEM_CENTRAL_DISCOVERY_PORT_CHECK_TIMEOUT_SECONDS` | `3` |
| TLS enabled | `GOLEM_CENTRAL_DISCOVERY_TLS_ENABLED` | `false` |
| Public IP for IP certificate | `GOLEM_CENTRAL_DISCOVERY_PUBLIC_IP` | `auto` |
| Public IP lookup URL | `GOLEM_CENTRAL_DISCOVERY_PUBLIC_IP_LOOKUP_URL` | `https://api.ipify.org` |
| ACME HTTP-01 host | `GOLEM_CENTRAL_DISCOVERY_ACME_HTTP_HOST` | `0.0.0.0` |
| ACME HTTP-01 port | `GOLEM_CENTRAL_DISCOVERY_ACME_HTTP_PORT` | `80` |
| ACME directory URL | `GOLEM_CENTRAL_DISCOVERY_ACME_DIRECTORY_URL` | `https://acme-v02.api.letsencrypt.org/directory` |
| ACME profile | `GOLEM_CENTRAL_DISCOVERY_ACME_PROFILE` | `shortlived` |
| ACME account email | `GOLEM_CENTRAL_DISCOVERY_ACME_ACCOUNT_EMAIL` | empty |
| Certificate directory | `GOLEM_CENTRAL_DISCOVERY_CERT_DIR` | `~/.golem/central-discovery/certs` |
| Renew before expiry | `GOLEM_CENTRAL_DISCOVERY_CERT_RENEW_BEFORE_HOURS` | `48` |
| Renewal check interval | `GOLEM_CENTRAL_DISCOVERY_CERT_RENEWAL_CHECK_INTERVAL_SECONDS` | `3600` |

## Built-in TLS for bare IP deployments

Central discovery can obtain and renew a Let's Encrypt IP certificate directly
from the binary. This mode uses ACME HTTP-01 validation on port 80 and serves
HTTPS/WSS on the configured service port, usually 443 for browser clients.

```bash
sudo GOLEM_CENTRAL_DISCOVERY_TLS_ENABLED=true \
  GOLEM_CENTRAL_DISCOVERY_PORT=443 \
  GOLEM_CENTRAL_DISCOVERY_PUBLIC_IP=94.130.182.147 \
  /usr/local/bin/golem-central-discovery
```

When `GOLEM_CENTRAL_DISCOVERY_PUBLIC_IP=auto`, the binary resolves the public IP
from `GOLEM_CENTRAL_DISCOVERY_PUBLIC_IP_LOOKUP_URL`. The HTTP-01 port must be
reachable publicly as port 80, and the service port must be reachable publicly
as the port used in client URLs. For a bare IP production requestor web deploy:

```bash
NEXT_PUBLIC_DISCOVERY_WS_URL=wss://94.130.182.147/api/v1/discovery/requestors
GOLEM_PROVIDER_DISCOVERY_WS_URL=wss://94.130.182.147/api/v1/discovery/providers
```

Providers derive their port-check URL from the discovery websocket origin by
default, so `wss://94.130.182.147/api/v1/discovery/providers` also means port
verification uses `https://94.130.182.147/check-ports` and
`https://94.130.182.147/check-tls`.

## Endpoints

- `GET /health`
- `POST /check-ports`
- `POST /check-tls`
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
