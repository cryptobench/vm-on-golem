# Discovery Architecture

Discovery is a live websocket capability. Providers are discoverable only while
their central-discovery provider websocket is connected, and requestors browse
providers through a requestor websocket subscription.

## Central Discovery

Central discovery keeps an in-memory registry keyed by provider ID. The registry
is connection-authoritative: provider disconnect removes that provider
immediately and broadcasts a removal to subscribed requestors.

HTTP is limited to `/health`. Discovery data is never read or written through
HTTP endpoints.

## Provider Flow

Provider nodes connect to:

```bash
GOLEM_PROVIDER_DISCOVERY_WS_URL=ws://host:9001/api/v1/discovery/providers
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

The requestor sends `subscribe` with resource, country, and platform filters.
The server responds with a `snapshot`, then streams `provider.upsert` and
`provider.remove` events. Filter changes send another `subscribe` message and
receive a fresh snapshot.

## Guarantees

- No stale providers survive provider disconnect.
- No persisted advertisement snapshot is queryable.
- No HTTP advertisement polling exists.
- No alternate discovery backend or compatibility alias exists.
