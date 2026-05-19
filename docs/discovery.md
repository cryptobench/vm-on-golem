# Discovery Architecture

Discovery is a live websocket capability. The central discovery binary also
serves the public port-check API used by providers to verify reachability, so
deployments only need one public service origin.

## Central Discovery

Central discovery keeps an in-memory registry keyed by provider ID. The registry
is connection-authoritative: provider disconnect removes that provider
immediately and broadcasts a removal to subscribed requestors.

HTTP is limited to `/health`, `/check-ports`, and `/check-tls`. Discovery data
is never read or written through HTTP endpoints.

## Port Verification

The same central discovery listener exposes:

```bash
POST /check-ports
POST /check-tls
```

Providers derive the HTTP(S) port-check origin from
`GOLEM_PROVIDER_DISCOVERY_WS_URL` by default. For example,
`wss://host/api/v1/discovery/providers` uses `https://host/check-ports` and
`https://host/check-tls`. `GOLEM_PROVIDER_PORT_CHECK_TLS_URL` remains available
as an explicit override.

## Provider Flow

Provider nodes connect to:

```bash
GOLEM_PROVIDER_DISCOVERY_WS_URL=ws://host:9001/api/v1/discovery/providers
```

For public browser-facing deployments, central discovery can serve TLS directly
with a Let's Encrypt IP certificate. In that case providers use the same path
with `wss://`, usually on port 443:

```bash
GOLEM_PROVIDER_DISCOVERY_WS_URL=wss://94.130.182.147/api/v1/discovery/providers
```

The server sends a nonce, the provider authenticates with an Ethereum signature
from `ETHEREUM_PRIVATE_KEY`, then sends `advertisement.upsert` whenever
resources, pricing, or endpoint state changes. If the endpoint is not
advertisable or resources fall below minimum requirements, the provider sends
`advertisement.remove`.

## Requestor Flow

Requestor web connects to:

```bash
NEXT_PUBLIC_DISCOVERY_WS_URL=ws://host:9001/api/v1/discovery/requestors
```

For HTTPS requestor-web deployments, use the TLS websocket URL:

```bash
NEXT_PUBLIC_DISCOVERY_WS_URL=wss://94.130.182.147/api/v1/discovery/requestors
```

The requestor sends `subscribe` with resource, country, and platform filters.
The server responds with a `snapshot`, then streams `provider.upsert` and
`provider.remove` events. Filter changes send another `subscribe` message and
receive a fresh snapshot.

## Guarantees

- No stale providers survive provider disconnect.
- No persisted advertisement snapshot is queryable.
- No HTTP advertisement polling exists.
- No alternate discovery backend or compatibility alias exists.
