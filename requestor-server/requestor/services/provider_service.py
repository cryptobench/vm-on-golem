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
        # Optional spec (cpu, memory, storage) to compute estimates for display
        self.estimate_spec: Optional[tuple[int, int, int]] = None

    def compute_estimate(self, provider: Dict, spec: tuple[int, int, int]) -> Optional[Dict]:
        """Compute estimated pricing for a given spec, if provider has pricing.

        Returns dict with usd_per_month, glm_per_month (if GLM per-unit available),
        and usd_per_hour, or None if insufficient pricing data.
        """
        pricing = provider.get('pricing') or {}
        usd_core = pricing.get('usd_per_core_month')
        usd_ram = pricing.get('usd_per_gb_ram_month')
        usd_storage = pricing.get('usd_per_gb_storage_month')
        if usd_core is None or usd_ram is None or usd_storage is None:
            return None
        cpu, mem, sto = spec
        try:
            usd_per_month = float(usd_core) * cpu + float(usd_ram) * mem + float(usd_storage) * sto
            glm_core = pricing.get('glm_per_core_month')
            glm_ram = pricing.get('glm_per_gb_ram_month')
            glm_storage = pricing.get('glm_per_gb_storage_month')
            glm_per_month = None
            if glm_core is not None and glm_ram is not None and glm_storage is not None:
                glm_per_month = float(glm_core) * cpu + float(glm_ram) * mem + float(glm_storage) * sto
            usd_per_hour = usd_per_month / 730.0
            # Round for display consistency
            return {
                'usd_per_month': round(usd_per_month, 4),
                'usd_per_hour': round(usd_per_hour, 6),
                'glm_per_month': round(glm_per_month, 8) if glm_per_month is not None else None,
            }
        except Exception:
            return None

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
        driver: Optional[str] = None,
        payments_network: Optional[str] = None,
        include_all_payments: bool = False,
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
            return await self._find_providers_golem_base(
                cpu, memory, storage, country,
                payments_network=payments_network,
                include_all_payments=include_all_payments,
            )
        else:
            return await self._find_providers_central(cpu, memory, storage, country)

    async def _find_providers_golem_base(
        self,
        cpu: Optional[int] = None,
        memory: Optional[int] = None,
        storage: Optional[int] = None,
        country: Optional[str] = None,
        payments_network: Optional[str] = None,
        include_all_payments: bool = False,
    ) -> List[Dict]:
        """Find providers using Golem Base."""
        try:
            def _to_float(val):
                if val is None:
                    return None
                try:
                    return float(val)
                except Exception:
                    return None

            query = 'golem_type="provider"'
            # Filter by advertised network to avoid cross-network results
            if config.network:
                query += f' && golem_network="{config.network}"'
            # Filter by payments network unless explicitly disabled
            pn = payments_network if payments_network is not None else getattr(config, 'payments_network', None)
            if pn and not include_all_payments:
                query += f' && golem_payments_network="{pn}"'
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
                    'payments_network': annotations.get('golem_payments_network'),
                    'resources': {
                        'cpu': int(annotations.get('golem_cpu', 0)),
                        'memory': int(annotations.get('golem_memory', 0)),
                        'storage': int(annotations.get('golem_storage', 0)),
                    },
                    'pricing': {
                        'usd_per_core_month': _to_float(annotations.get('golem_price_usd_core_month')),
                        'usd_per_gb_ram_month': _to_float(annotations.get('golem_price_usd_ram_gb_month')),
                        'usd_per_gb_storage_month': _to_float(annotations.get('golem_price_usd_storage_gb_month')),
                        'glm_per_core_month': _to_float(annotations.get('golem_price_glm_core_month')),
                        'glm_per_gb_ram_month': _to_float(annotations.get('golem_price_glm_ram_gb_month')),
                        'glm_per_gb_storage_month': _to_float(annotations.get('golem_price_glm_storage_gb_month')),
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

        pricing = provider.get('pricing') or {}
        usd_core = pricing.get('usd_per_core_month')
        usd_ram = pricing.get('usd_per_gb_ram_month')
        usd_storage = pricing.get('usd_per_gb_storage_month')

        # Precompute estimates if a spec is set and pricing available
        est_usd = '—'
        est_glm = '—'
        est_hr_usd = '—'
        if self.estimate_spec and all(p is not None for p in (usd_core, usd_ram, usd_storage)):
            spec_cpu, spec_mem, spec_sto = self.estimate_spec
            try:
                est_usd_val = (float(usd_core) * spec_cpu) + (float(usd_ram) * spec_mem) + (float(usd_storage) * spec_sto)
                est_usd = round(est_usd_val, 4)
                est_hr_usd = round(est_usd_val / 730.0, 6)
                # If GLM per-unit is present, compute GLM estimate as well
                glm_core = pricing.get('glm_per_core_month')
                glm_ram = pricing.get('glm_per_gb_ram_month')
                glm_storage = pricing.get('glm_per_gb_storage_month')
                if all(x is not None for x in (glm_core, glm_ram, glm_storage)):
                    est_glm_val = (float(glm_core) * spec_cpu) + (float(glm_ram) * spec_mem) + (float(glm_storage) * spec_sto)
                    est_glm = round(est_glm_val, 8)
            except Exception:
                pass

        row = [
            provider['provider_id'],
            provider['provider_name'],
            provider['ip_address'] or 'N/A',
            provider['country'],
            provider['resources']['cpu'],
            provider['resources']['memory'],
            provider['resources']['storage'],
            usd_core if usd_core is not None else '—',
            usd_ram if usd_ram is not None else '—',
            usd_storage if usd_storage is not None else '—',
            est_usd,
            est_glm,
            updated_at_str
        ]

        if colorize:
            # Format Provider ID
            id_txt = style(row[0], fg="yellow")
            if est_hr_usd != '—':
                id_txt += style(f"  (~${est_hr_usd}/hr)", fg="yellow")
            row[0] = id_txt

            # Format resources with icons and colors
            row[4] = style(f"💻 {row[4]}", fg="cyan", bold=True)
            row[5] = style(f"🧠 {row[5]}", fg="cyan", bold=True)
            row[6] = style(f"💾 {row[6]}", fg="cyan", bold=True)

            # Format pricing with currency markers
            if usd_core != '—':
                row[7] = style(f"${row[7]}/mo", fg="magenta")
            if usd_ram != '—':
                row[8] = style(f"${row[8]}/GB/mo", fg="magenta")
            if usd_storage != '—':
                row[9] = style(f"${row[9]}/GB/mo", fg="magenta")
            if est_usd != '—':
                row[10] = style(f"~${row[10]}/mo", fg="yellow", bold=True)
            if est_glm != '—':
                row[11] = style(f"~{row[11]} GLM/mo", fg="yellow")

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
            "Disk (GB)",
            "USD/core/mo",
            "USD/GB RAM/mo",
            "USD/GB Disk/mo",
            "Est. $/mo",
            "Est. GLM/mo",
            "Updated"
        ]
