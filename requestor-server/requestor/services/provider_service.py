"""Provider discovery and management service."""
from typing import Dict, List, Optional
import aiohttp
from ..errors import DiscoveryError, ProviderError
from ..config import config

class ProviderService:
    """Service for provider operations."""
    
    def __init__(self, discovery_url: str):
        self.discovery_url = discovery_url
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def find_providers(
        self,
        cpu: Optional[int] = None,
        memory: Optional[int] = None,
        storage: Optional[int] = None,
        country: Optional[str] = None
    ) -> List[Dict]:
        """Find providers matching requirements."""
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
                f"{self.discovery_url}/api/v1/advertisements",
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
            raise DiscoveryError(f"Failed to connect to discovery service: {str(e)}")
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

    def format_provider_row(self, provider: Dict, colorize: bool = False) -> List:
        """Format provider information for display."""
        from click import style

        row = [
            provider['provider_id'],
            provider['ip_address'] or 'N/A',
            provider['country'],
            provider['resources']['cpu'],
            provider['resources']['memory'],
            provider['resources']['storage'],
            provider['updated_at']
        ]

        if colorize:
            # Format Provider ID
            row[0] = style(row[0], fg="yellow")
            
            # Format resources with icons and colors
            row[3] = style(f"💻 {row[3]}", fg="cyan", bold=True)
            row[4] = style(f"🧠 {row[4]}", fg="cyan", bold=True)
            row[5] = style(f"💾 {row[5]}", fg="cyan", bold=True)
            
            # Format location info
            row[2] = style(f"🌍 {row[2]}", fg="green", bold=True)

        return row

    @property
    def provider_headers(self) -> List[str]:
        """Get headers for provider display."""
        return [
            "Provider ID",
            "IP Address", 
            "Country",
            "CPU",
            "Memory (GB)",
            "Storage (GB)",
            "Updated"
        ]
