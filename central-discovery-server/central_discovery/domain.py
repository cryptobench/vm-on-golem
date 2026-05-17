from datetime import datetime
from typing import Dict, Literal, Optional

from pydantic import BaseModel, Field, validator

from central_discovery.time import ensure_utc, utc_now


class ResourceRequirements(BaseModel):
    cpu: Optional[int] = Field(None, ge=1)
    memory: Optional[int] = Field(None, ge=1)
    storage: Optional[int] = Field(None, ge=1)
    country: Optional[str] = Field(None, min_length=2, max_length=2)
    platform: Optional[str] = None


class AdvertisementPayload(BaseModel):
    ip_address: str = Field(..., regex=r"^(\d{1,3}\.){3}\d{1,3}$")
    country: str = Field(..., min_length=2, max_length=2)
    platform: Optional[str] = None
    endpoint_protocol: Optional[str] = None
    endpoint_host: Optional[str] = None
    endpoint_port: Optional[int] = Field(None, ge=1, le=65535)
    endpoint_url: Optional[str] = None
    resources: Dict[str, int]
    pricing: Optional[Dict] = None

    @validator("resources")
    def validate_resources(cls, value):
        required = {"cpu", "memory", "storage"}
        missing = required.difference(value)
        if missing:
            raise ValueError(f"Missing required resources: {sorted(missing)}")
        for key in required:
            if value[key] < 1:
                raise ValueError(f"{key} must be >= 1")
        return value


class Advertisement(AdvertisementPayload):
    provider_id: str
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @validator("created_at", "updated_at", pre=True)
    def ensure_timestamp_timezone(cls, value):
        return ensure_utc(value) if isinstance(value, datetime) else value


class ProviderAuthenticateMessage(BaseModel):
    type: Literal["authenticate"]
    provider_id: str
    nonce: str
    timestamp: datetime
    signature: str

    @validator("timestamp", pre=True)
    def ensure_timestamp_timezone(cls, value):
        return ensure_utc(value) if isinstance(value, datetime) else value


class ProviderUpsertMessage(BaseModel):
    type: Literal["advertisement.upsert"]
    advertisement: AdvertisementPayload


class ProviderRemoveMessage(BaseModel):
    type: Literal["advertisement.remove"]


class RequestorSubscribeMessage(BaseModel):
    type: Literal["subscribe"]
    filters: ResourceRequirements = Field(default_factory=ResourceRequirements)


class HealthResponse(BaseModel):
    status: str


class DiscoveryError(Exception):
    pass


class UnauthorizedError(DiscoveryError):
    pass


class ProtocolError(DiscoveryError):
    pass
