from pydantic import BaseModel, Field


class ResourceSettings(BaseModel):
    cpu: int = Field(..., ge=0)
    memory: int = Field(..., ge=0)
    storage: int = Field(..., ge=0)


class UpdateResourceSettings(BaseModel):
    cpu: int = Field(..., ge=1)
    memory: int = Field(..., ge=1)
    storage: int = Field(..., ge=1)


class PricingSettings(BaseModel):
    usd_per_core_month: float = Field(..., ge=0)
    usd_per_gb_ram_month: float = Field(..., ge=0)
    usd_per_gb_storage_month: float = Field(..., ge=0)
    glm_per_core_month: float = Field(..., ge=0)
    glm_per_gb_ram_month: float = Field(..., ge=0)
    glm_per_gb_storage_month: float = Field(..., ge=0)
    warning: str | None = None


class UpdatePricingSettings(BaseModel):
    usd_per_core_month: float = Field(..., ge=0)
    usd_per_gb_ram_month: float = Field(..., ge=0)
    usd_per_gb_storage_month: float = Field(..., ge=0)


class ProviderSettings(BaseModel):
    detected_resources: ResourceSettings
    offered_resources: ResourceSettings
    allocated_resources: ResourceSettings
    available_resources: ResourceSettings
    minimum_configurable_resources: ResourceSettings
    pricing: PricingSettings
