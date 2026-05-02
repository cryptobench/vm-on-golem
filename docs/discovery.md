# Discovery Architecture

Discovery is the capability that lets providers publish available capacity and lets requestors find providers. VM on Golem supports two discovery backends.

## Backends

| Backend | Mode | Purpose |
| --- | --- | --- |
| Arkiv | Decentralized Web3 database | Default backend. Providers publish advertisements as Arkiv entities, and requestors query Arkiv by annotations. |
| Central Discovery | FastAPI + SQLite service | Legacy/self-hosted backend. Providers POST advertisements to an HTTP server, and requestors query that server. |

The old name “discovery-server” referred only to the centralized MVP backend. It is now named `central-discovery-server` to avoid implying it is the whole discovery system.

## Provider Flow

Provider-side discovery publishing is selected with:

```bash
GOLEM_PROVIDER_DISCOVERY_BACKEND=arkiv   # default
GOLEM_PROVIDER_DISCOVERY_BACKEND=central
GOLEM_PROVIDER_DISCOVERY_BACKEND=both
```

Legacy `GOLEM_PROVIDER_ADVERTISER_TYPE=golem_base|discovery_server|both` is still accepted.

Canonical provider classes:

- `ArkivDiscoveryPublisher` publishes to Arkiv.
- `CentralDiscoveryPublisher` publishes to the centralized HTTP service.
- `CompositeDiscoveryPublisher` publishes to both.
- `DiscoveryPublishingService` owns lifecycle and immediate update triggering.

## Requestor Flow

Requestor-side provider lookup is selected with:

```bash
GOLEM_REQUESTOR_DISCOVERY_BACKEND=arkiv   # default
GOLEM_REQUESTOR_DISCOVERY_BACKEND=central
```

Legacy `GOLEM_REQUESTOR_DISCOVERY_DRIVER=golem-base|central` is still accepted.

Canonical requestor clients:

- `ArkivDiscoveryClient` queries Arkiv annotations.
- `CentralDiscoveryClient` queries `/api/v1/advertisements`.
- `ProviderService` delegates discovery lookup to the selected client and keeps higher-level provider operations stable.

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
