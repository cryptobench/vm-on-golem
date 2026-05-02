"""Discovery domain DTOs used by requestor-side discovery adapters."""

from typing import Optional

from pydantic import BaseModel


class ProviderSearchQuery(BaseModel):
    cpu: Optional[int] = None
    memory: Optional[int] = None
    storage: Optional[int] = None
    country: Optional[str] = None
    platform: Optional[str] = None
    payments_network: Optional[str] = None
    include_all_payments: bool = False


class ProviderResources(BaseModel):
    cpu: int = 0
    memory: int = 0
    storage: int = 0


class ProviderPricing(BaseModel):
    usd_per_core_month: float | None = None
    usd_per_gb_ram_month: float | None = None
    usd_per_gb_storage_month: float | None = None
    glm_per_core_month: float | None = None
    glm_per_gb_ram_month: float | None = None
    glm_per_gb_storage_month: float | None = None


class ProviderAdvertisement(BaseModel):
    provider_id: str
    provider_name: str | None = None
    ip_address: str | None = None
    country: str | None = None
    platform: str | None = None
    payments_network: str | None = None
    resources: ProviderResources
    pricing: ProviderPricing | None = None
    created_at_block: int | None = None


class ProviderListResponse(BaseModel):
    providers: list[ProviderAdvertisement]


class ProviderEstimate(BaseModel):
    usd_per_month: float
    usd_per_hour: float
    glm_per_month: float | None = None
