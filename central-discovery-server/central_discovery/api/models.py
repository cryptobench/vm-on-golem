from datetime import datetime
from typing import Dict, Optional

from pydantic import BaseModel, Field, constr, validator

from central_discovery.time import ensure_utc, utc_now


class ResourceRequirements(BaseModel):
    """Resource requirements for querying advertisements."""

    cpu: Optional[int] = Field(None, ge=1, description="Minimum CPU cores required")
    memory: Optional[int] = Field(
        None, ge=1, description="Minimum memory (GB) required"
    )
    storage: Optional[int] = Field(
        None, ge=1, description="Minimum storage (GB) required"
    )


class AdvertisementCreate(BaseModel):
    """Model for creating/updating an advertisement."""

    ip_address: str = Field(..., regex=r"^(\d{1,3}\.){3}\d{1,3}$")
    country: constr(min_length=2, max_length=2) = Field(
        ..., description="ISO 3166-1 alpha-2 country code"
    )
    platform: Optional[str] = Field(
        None, description="Provider platform/architecture (e.g., x86_64, arm64)"
    )
    endpoint_protocol: Optional[str] = Field(
        None, description="Provider public endpoint protocol"
    )
    endpoint_host: Optional[str] = Field(
        None, description="Provider public endpoint host"
    )
    endpoint_port: Optional[int] = Field(
        None, ge=1, le=65535, description="Provider public endpoint port"
    )
    endpoint_url: Optional[str] = Field(
        None, description="Provider public endpoint URL"
    )
    resources: Dict[str, int] = Field(
        ..., description="Available resources (cpu, memory, storage)"
    )
    pricing: Optional[Dict] = Field(
        None, description="Pricing info (USD and GLM per-unit monthly)"
    )

    @validator("resources")
    def validate_resources(cls, v):
        """Validate resource dictionary."""
        required_keys = {"cpu", "memory", "storage"}
        if not all(k in v for k in required_keys):
            raise ValueError(f"Missing required resources: {required_keys}")

        # Validate resource values
        if v["cpu"] < 1:
            raise ValueError("CPU cores must be >= 1")
        if v["memory"] < 1:
            raise ValueError("Memory must be >= 1 GB")
        if v["storage"] < 1:
            raise ValueError("Storage must be >= 1 GB")

        return v


class AdvertisementResponse(BaseModel):
    """Model for advertisement responses."""

    provider_id: str
    ip_address: str
    country: str
    platform: Optional[str]
    endpoint_protocol: Optional[str]
    endpoint_host: Optional[str]
    endpoint_port: Optional[int]
    endpoint_url: Optional[str]
    resources: Dict[str, int]
    pricing: Optional[Dict]
    created_at: datetime
    updated_at: datetime

    @validator("created_at", "updated_at", pre=True)
    def ensure_timestamp_timezone(cls, value):
        return ensure_utc(value) if isinstance(value, datetime) else value

    class Config:
        orm_mode = True


class ErrorResponse(BaseModel):
    """Model for error responses."""

    code: str
    message: str
    timestamp: datetime = Field(default_factory=utc_now)


class DeleteAdvertisementResponse(BaseModel):
    status: str


class HealthResponse(BaseModel):
    status: str
