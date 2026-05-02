from requestor.config import RequestorConfig
from requestor.errors import NotFoundError

from .backends import (
    ArkivDiscoveryClient,
    CentralDiscoveryClient,
    normalize_discovery_backend,
)
from .domain import ProviderEstimate, ProviderSearchQuery


class ProviderDiscoveryService:
    """Application-facing provider lookup service."""

    def __init__(
        self,
        settings: RequestorConfig,
        arkiv_client: ArkivDiscoveryClient,
        central_client: CentralDiscoveryClient,
    ):
        self.settings = settings
        self.arkiv_client = arkiv_client
        self.central_client = central_client

    async def close(self) -> None:
        await self.arkiv_client.close()
        central_session = getattr(self.central_client, "session", None)
        if central_session is not None and not central_session.closed:
            await central_session.close()

    async def find_providers(
        self, query: ProviderSearchQuery, backend: str | None = None
    ) -> list[dict]:
        selected = normalize_discovery_backend(
            backend or self.settings.discovery_backend
        )
        if selected == "arkiv":
            return await self.arkiv_client.find_providers(query)
        return await self.central_client.find_providers(query)

    async def require_provider(
        self, provider_id: str, query: ProviderSearchQuery | None = None
    ) -> dict:
        providers = await self.find_providers(query or ProviderSearchQuery())
        for provider in providers:
            if provider.get("provider_id") == provider_id:
                return provider
        raise NotFoundError(f"Provider {provider_id} not found")

    async def has_resources(
        self, provider_id: str, cpu: int, memory: int, storage: int
    ) -> bool:
        provider = await self.require_provider(provider_id)
        resources = provider.get("resources") or {}
        return (
            int(resources.get("cpu", 0)) >= cpu
            and int(resources.get("memory", 0)) >= memory
            and int(resources.get("storage", 0)) >= storage
        )

    @staticmethod
    def compute_estimate(
        provider: dict, spec: tuple[int, int, int]
    ) -> ProviderEstimate | None:
        pricing = provider.get("pricing") or {}
        usd_core = pricing.get("usd_per_core_month")
        usd_ram = pricing.get("usd_per_gb_ram_month")
        usd_storage = pricing.get("usd_per_gb_storage_month")
        if usd_core is None or usd_ram is None or usd_storage is None:
            return None
        cpu, memory, storage = spec
        usd_per_month = (
            float(usd_core) * cpu
            + float(usd_ram) * memory
            + float(usd_storage) * storage
        )
        glm_per_month = None
        glm_core = pricing.get("glm_per_core_month")
        glm_ram = pricing.get("glm_per_gb_ram_month")
        glm_storage = pricing.get("glm_per_gb_storage_month")
        if glm_core is not None and glm_ram is not None and glm_storage is not None:
            glm_per_month = (
                float(glm_core) * cpu
                + float(glm_ram) * memory
                + float(glm_storage) * storage
            )
        return ProviderEstimate(
            usd_per_month=round(usd_per_month, 4),
            usd_per_hour=round(usd_per_month / 730.0, 6),
            glm_per_month=round(glm_per_month, 8)
            if glm_per_month is not None
            else None,
        )
