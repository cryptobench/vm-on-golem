# Discovery Architecture

Discovery is the capability that lets providers publish available capacity and lets requestors find providers. VM on Golem supports two discovery backends.

## Backends

| Backend | Mode | Purpose |
| --- | --- | --- |
| Central Discovery | FastAPI + SQLite service | Default backend. Providers POST advertisements to an HTTP server, and requestors query that server. |
| Arkiv | Decentralized Web3 database | Optional decentralized backend. Providers publish advertisements as Arkiv entities, and requestors query Arkiv by annotations. |

The old name “discovery-server” referred only to the centralized MVP backend. It is now named `central-discovery-server` to avoid implying it is the whole discovery system.

## Provider Flow

Provider-side discovery publishing is selected with:

```bash
GOLEM_PROVIDER_DISCOVERY_BACKEND=central # default
GOLEM_PROVIDER_DISCOVERY_BACKEND=arkiv
GOLEM_PROVIDER_DISCOVERY_BACKEND=both
```

Legacy `GOLEM_PROVIDER_ADVERTISER_TYPE=golem_base|discovery_server|both` is still accepted.

Canonical provider classes:

- `ArkivDiscoveryPublisher` publishes to Arkiv.
- `CentralDiscoveryPublisher` publishes to the centralized HTTP service.
- `CompositeDiscoveryPublisher` publishes to both.
- `DiscoveryPublishingService` owns lifecycle and immediate update triggering.

Advertisements carry both legacy `ip_address` and public endpoint metadata. In
production, providers publish `endpoint_protocol=https`, `endpoint_host`,
`endpoint_port`, and `endpoint_url` after verifying the public IP HTTPS
certificate. In development, providers may publish an HTTP endpoint for local
direct access. Requestor clients require a usable `endpoint_url` for provider
API traffic. `ip_address` remains legacy metadata and may still be used for SSH
host display, but it is not a provider API fallback.

## Requestor Flow

Requestor web provider lookup is selected with:

```bash
NEXT_PUBLIC_DISCOVERY_MODE=central # default
NEXT_PUBLIC_DISCOVERY_MODE=arkiv
```

Requestor web hides advertisements without a usable `endpoint_url`. HTTP
endpoints are accepted only in development; production requestor clients require
HTTPS.

## Naming

Use these terms consistently:

- `discovery`: the capability/domain.
- `Arkiv`: the decentralized Web3 database backend.
- `central discovery`: the centralized FastAPI backend.
- `central-discovery-server`: the package containing the centralized backend.

Compatibility aliases remain for one transition window:

- `GolemBaseAdvertiser` -> `ArkivDiscoveryPublisher`
- `DiscoveryServerAdvertiser` -> `CentralDiscoveryPublisher`
- `MultiAdvertiser` -> `CompositeDiscoveryPublisher`
- `golem-discovery` -> `golem-central-discovery`
- `GOLEM_DISCOVERY_*` -> `GOLEM_CENTRAL_DISCOVERY_*`
