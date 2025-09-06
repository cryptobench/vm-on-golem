"""Provider discovery and management service."""
from typing import Dict, List, Optional
import aiohttp
import time
from datetime import datetime, timezone
from ..errors import DiscoveryError, ProviderError
from ..config import config
from golem_base_sdk import GolemBaseClient
from golem_base_sdk.types import EntityKey, GenericBytes


class ProviderService:
    """Service for provider operations."""

    def __init__(self):
        self.session = None
        self.golem_base_client = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        # The GolemBaseClient is now initialized on-demand in find_providers
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
        if self.golem_base_client:
            await self.golem_base_client.disconnect()

    async def find_providers(
        self,
        cpu: Optional[int] = None,
        memory: Optional[int] = None,
        storage: Optional[int] = None,
        country: Optional[str] = None,
        driver: Optional[str] = None
    ) -> List[Dict]:
        """Find providers matching requirements."""
        discovery_driver = driver or config.discovery_driver
        if discovery_driver == "golem-base":
            if not self.golem_base_client:
                private_key_hex = config.ethereum_private_key.replace("0x", "")
                private_key_bytes = bytes.fromhex(private_key_hex)
                self.golem_base_client = await GolemBaseClient.create(
                    rpc_url=config.golem_base_rpc_url,
                    ws_url=config.golem_base_ws_url,
                    private_key=private_key_bytes,
                )
            return await self._find_providers_golem_base(cpu, memory, storage, country)
        else:
            return await self._find_providers_central(cpu, memory, storage, country)

    async def _find_providers_golem_base(
        self,
        cpu: Optional[int] = None,
        memory: Optional[int] = None,
        storage: Optional[int] = None,
        country: Optional[str] = None
    ) -> List[Dict]:
        """Find providers using Golem Base."""
        try:
            query = 'golem_type="provider"'
            if cpu:
                query += f' && golem_cpu>={cpu}'
            if memory:
                query += f' && golem_memory>={memory}'
            if storage:
                query += f' && golem_storage>={storage}'
            if country:
                query += f' && golem_country="{country}"'

            results = await self.golem_base_client.query_entities(query)

            providers = []
            for result in results:
                entity_key = EntityKey(
                    GenericBytes.from_hex_string(result.entity_key)
                )
                metadata = await self.golem_base_client.get_entity_metadata(entity_key)
                annotations = {
                    ann.key: ann.value for ann in metadata.string_annotations}
                annotations.update(
                    {ann.key: ann.value for ann in metadata.numeric_annotations})
                provider = {
                    'provider_id': annotations.get('golem_provider_id'),
                    'provider_name': annotations.get('golem_provider_name'),
                    'ip_address': annotations.get('golem_ip_address'),
                    'country': annotations.get('golem_country'),
                    'resources': {
                        'cpu': int(annotations.get('golem_cpu', 0)),
                        'memory': int(annotations.get('golem_memory', 0)),
                        'storage': int(annotations.get('golem_storage', 0)),
                    },
                    'created_at_block': metadata.expires_at_block - (config.advertisement_interval * 2)
                }
                if provider['provider_id']:
                    providers.append(provider)

            return providers
        except Exception as e:
            raise DiscoveryError(
                f"Error finding providers on Golem Base: {str(e)}")

    async def _find_providers_central(
        self,
        cpu: Optional[int] = None,
        memory: Optional[int] = None,
        storage: Optional[int] = None,
        country: Optional[str] = None
    ) -> List[Dict]:
        """Find providers using the central discovery service."""
        try:
            # Build query parameters
            params = {
                k: v for k, v in {
                    'cpu': cpu,
                    'memory': memory,
                    'storage': storage,
                    'country': country
                }.items() if v is not None
            }

            # Query discovery service
            async with self.session.get(
                f"{config.discovery_url}/api/v1/advertisements",
                params=params
            ) as response:
                if not response.ok:
                    raise DiscoveryError(
                        f"Failed to query discovery service: {await response.text()}"
                    )
                providers = await response.json()

            # Process provider IPs based on environment
            for provider in providers:
                provider['ip_address'] = (
                    'localhost' if config.environment == "development"
                    else provider.get('ip_address')
                )

            return providers

        except aiohttp.ClientError as e:
            raise DiscoveryError(
                f"Failed to connect to discovery service: {str(e)}")
        except Exception as e:
            raise DiscoveryError(f"Error finding providers: {str(e)}")

    async def verify_provider(self, provider_id: str) -> Dict:
        """Verify provider exists and is available."""
        try:
            providers = await self.find_providers()
            provider = next(
                (p for p in providers if p['provider_id'] == provider_id),
                None
            )

            if not provider:
                raise ProviderError(f"Provider {provider_id} not found")

            return provider

        except Exception as e:
            if isinstance(e, ProviderError):
                raise
            raise ProviderError(f"Failed to verify provider: {str(e)}")

    async def get_provider_resources(self, provider_id: str) -> Dict:
        """Get current resource availability for a provider."""
        try:
            provider = await self.verify_provider(provider_id)
            return {
                'cpu': provider['resources']['cpu'],
                'memory': provider['resources']['memory'],
                'storage': provider['resources']['storage']
            }
        except Exception as e:
            raise ProviderError(f"Failed to get provider resources: {str(e)}")

    async def check_resource_availability(
        self,
        provider_id: str,
        cpu: int,
        memory: int,
        storage: int
    ) -> bool:
        """Check if provider has sufficient resources."""
        try:
            resources = await self.get_provider_resources(provider_id)

            return (
                resources['cpu'] >= cpu and
                resources['memory'] >= memory and
                resources['storage'] >= storage
            )

        except Exception as e:
            raise ProviderError(
                f"Failed to check resource availability: {str(e)}"
            )

    async def _format_block_timestamp(self, block_number: int) -> str:
        """Format a block number into a human-readable 'time ago' string."""
        if not self.golem_base_client:
            return "N/A"
        try:
            latest_block = await self.golem_base_client.http_client().eth.get_block('latest')
            block_diff = latest_block.number - block_number
            seconds_ago = block_diff * 2  # Approximate block time
            
            if seconds_ago < 60:
                return f"{int(seconds_ago)}s ago"
            elif seconds_ago < 3600:
                return f"{int(seconds_ago / 60)}m ago"
            elif seconds_ago < 86400:
                return f"{int(seconds_ago / 3600)}h ago"
            else:
                return f"{int(seconds_ago / 86400)}d ago"
        except Exception:
            return "N/A"

    async def format_provider_row(self, provider: Dict, colorize: bool = False) -> List:
        """Format provider information for display."""
        from click import style

        updated_at_str = await self._format_block_timestamp(provider.get('created_at_block', 0))

        row = [
            provider['provider_id'],
            provider['provider_name'],
            provider['ip_address'] or 'N/A',
            provider['country'],
            provider['resources']['cpu'],
            provider['resources']['memory'],
            provider['resources']['storage'],
            updated_at_str
        ]

        if colorize:
            # Format Provider ID
            row[0] = style(row[0], fg="yellow")

            # Format resources with icons and colors
            row[4] = style(f"💻 {row[4]}", fg="cyan", bold=True)
            row[5] = style(f"🧠 {row[5]}", fg="cyan", bold=True)
            row[6] = style(f"💾 {row[6]}", fg="cyan", bold=True)

            # Format location info
            row[3] = style(f"🌍 {row[3]}", fg="green", bold=True)

        return row

    @property
    def provider_headers(self) -> List[str]:
        """Get headers for provider display."""
        return [
            "Provider ID",
            "Name",
            "IP Address",
            "Country",
            "CPU",
            "Memory (GB)",
            "Storage (GB)",
            "Updated"
        ]
