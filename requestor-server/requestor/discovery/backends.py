"""Requestor-side provider discovery backends."""

from typing import Dict, List, Optional

import aiohttp
from golem_base_sdk.types import EntityKey, GenericBytes

from ..config import config
from ..errors import DiscoveryError
from .domain import ProviderSearchQuery


def normalize_discovery_backend(value: Optional[str]) -> str:
    raw = (value or "").strip().lower().replace("_", "-")
    if raw in {"arkiv", "golem-base", "golembase"}:
        return "arkiv"
    if raw in {"", "central", "discovery-server", "discovery"}:
        return "central"
    raise DiscoveryError("Discovery backend must be 'arkiv' or 'central'")


class CentralDiscoveryClient:
    """Find providers through the centralized HTTP discovery service."""

    def __init__(self, session: aiohttp.ClientSession | None = None):
        self.session = session

    async def find_providers(self, query: ProviderSearchQuery) -> List[Dict]:
        if self.session is None:
            async with aiohttp.ClientSession() as session:
                return await self._find_providers_with_session(session, query)
        return await self._find_providers_with_session(self.session, query)

    async def _find_providers_with_session(
        self, session: aiohttp.ClientSession, query: ProviderSearchQuery
    ) -> List[Dict]:
        try:
            params = {
                k: v
                for k, v in {
                    "cpu": query.cpu,
                    "memory": query.memory,
                    "storage": query.storage,
                    "country": query.country,
                    "platform": query.platform,
                }.items()
                if v is not None
            }

            async with session.get(
                f"{config.discovery_url}/api/v1/advertisements",
                params=params,
            ) as response:
                if not response.ok:
                    raise DiscoveryError(
                        f"Failed to query central discovery: {await response.text()}"
                    )
                providers = await response.json()

            for provider in providers:
                provider["ip_address"] = (
                    "localhost"
                    if config.environment == "development"
                    else provider.get("ip_address")
                )

            return providers
        except aiohttp.ClientError as e:
            raise DiscoveryError(f"Failed to connect to central discovery: {str(e)}")
        except Exception as e:
            if isinstance(e, DiscoveryError):
                raise
            raise DiscoveryError(
                f"Error finding providers via central discovery: {str(e)}"
            )


class ArkivDiscoveryClient:
    """Find providers through Arkiv, the decentralized discovery backend."""

    def __init__(self, client_factory):
        self.client_factory = client_factory
        self.client = None

    async def close(self) -> None:
        if self.client:
            await self.client.disconnect()

    async def _ensure_client(self):
        if self.client is None:
            private_key_hex = config.ethereum_private_key.replace("0x", "")
            private_key_bytes = bytes.fromhex(private_key_hex)
            self.client = await self.client_factory.create(
                rpc_url=config.arkiv_rpc_url,
                ws_url=config.arkiv_ws_url,
                private_key=private_key_bytes,
            )
        return self.client

    async def find_providers(self, query: ProviderSearchQuery) -> List[Dict]:
        try:
            client = await self._ensure_client()
            arkiv_query = self._build_query(query)
            results = await client.query_entities(arkiv_query)

            providers = []
            for result in results:
                entity_key = EntityKey(GenericBytes.from_hex_string(result.entity_key))
                metadata = await client.get_entity_metadata(entity_key)
                annotations = {
                    ann.key: ann.value for ann in metadata.string_annotations
                }
                annotations.update(
                    {ann.key: ann.value for ann in metadata.numeric_annotations}
                )
                provider = {
                    "provider_id": annotations.get("golem_provider_id"),
                    "provider_name": annotations.get("golem_provider_name"),
                    "ip_address": annotations.get("golem_ip_address"),
                    "endpoint_protocol": annotations.get("golem_endpoint_protocol"),
                    "endpoint_host": annotations.get("golem_endpoint_host"),
                    "endpoint_port": self._to_int(
                        annotations.get("golem_endpoint_port")
                    ),
                    "endpoint_url": annotations.get("golem_endpoint_url"),
                    "country": annotations.get("golem_country"),
                    "platform": annotations.get("golem_platform") or None,
                    "payments_network": annotations.get("golem_payments_network"),
                    "resources": {
                        "cpu": int(annotations.get("golem_cpu", 0)),
                        "memory": int(annotations.get("golem_memory", 0)),
                        "storage": int(annotations.get("golem_storage", 0)),
                    },
                    "pricing": {
                        "usd_per_core_month": self._to_float(
                            annotations.get("golem_price_usd_core_month")
                        ),
                        "usd_per_gb_ram_month": self._to_float(
                            annotations.get("golem_price_usd_ram_gb_month")
                        ),
                        "usd_per_gb_storage_month": self._to_float(
                            annotations.get("golem_price_usd_storage_gb_month")
                        ),
                        "glm_per_core_month": self._to_float(
                            annotations.get("golem_price_glm_core_month")
                        ),
                        "glm_per_gb_ram_month": self._to_float(
                            annotations.get("golem_price_glm_ram_gb_month")
                        ),
                        "glm_per_gb_storage_month": self._to_float(
                            annotations.get("golem_price_glm_storage_gb_month")
                        ),
                    },
                    "created_at_block": metadata.expires_at_block
                    - (config.advertisement_interval * 2),
                }
                if provider["provider_id"]:
                    providers.append(provider)

            return providers
        except Exception as e:
            raise DiscoveryError(f"Error finding providers on Arkiv: {str(e)}")

    def _build_query(self, query: ProviderSearchQuery) -> str:
        arkiv_query = 'golem_type="provider"'
        if config.network:
            arkiv_query += f' && golem_network="{config.network}"'
        payments_network = (
            query.payments_network
            if query.payments_network is not None
            else getattr(config, "payments_network", None)
        )
        if payments_network and not query.include_all_payments:
            arkiv_query += f' && golem_payments_network="{payments_network}"'
        if query.cpu:
            arkiv_query += f" && golem_cpu>={query.cpu}"
        if query.memory:
            arkiv_query += f" && golem_memory>={query.memory}"
        if query.storage:
            arkiv_query += f" && golem_storage>={query.storage}"
        if query.country:
            arkiv_query += f' && golem_country="{query.country}"'
        if query.platform:
            arkiv_query += f' && golem_platform="{query.platform}"'
        return arkiv_query

    @staticmethod
    def _to_float(val):
        if val is None:
            return None
        try:
            return float(val)
        except Exception:
            return None

    @staticmethod
    def _to_int(val):
        if val is None:
            return None
        try:
            return int(val)
        except Exception:
            return None
