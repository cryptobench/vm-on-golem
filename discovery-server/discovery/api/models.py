from pydantic import BaseModel, Field, validator, constr
from typing import Dict, Optional
from datetime import datetime

class ResourceRequirements(BaseModel):
    """Resource requirements for querying advertisements."""
    cpu: Optional[int] = Field(None, ge=1, description="Minimum CPU cores required")
    memory: Optional[int] = Field(None, ge=1, description="Minimum memory (GB) required")
    storage: Optional[int] = Field(None, ge=1, description="Minimum storage (GB) required")

class AdvertisementCreate(BaseModel):
    """Model for creating/updating an advertisement."""
    ip_address: str = Field(..., regex=r"^(\d{1,3}\.){3}\d{1,3}$")
    country: constr(min_length=2, max_length=2) = Field(
        ...,
        description="ISO 3166-1 alpha-2 country code"
    )
    resources: Dict[str, int] = Field(
        ...,
        description="Available resources (cpu, memory, storage)"
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
    resources: Dict[str, int]
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

class ErrorResponse(BaseModel):
    """Model for error responses."""
    code: str
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
