from pydantic import BaseModel, Field, validator
from typing import Dict, Optional, List, Any
from datetime import datetime

from ..vm.models import VMSize, VMResources, VMStatus

class CreateVMRequest(BaseModel):
    """Request model for creating a VM."""
    name: str = Field(..., min_length=3, max_length=64, regex="^[a-z0-9][a-z0-9-]*[a-z0-9]$")
    size: Optional[VMSize] = None
    resources: Optional[VMResources] = None
    image: str = Field(default="20.04")  # Ubuntu 20.04 LTS
    ssh_key: str = Field(..., regex="^(ssh-rsa|ssh-ed25519) ", description="SSH public key for VM access")

    @validator("resources", pre=True, always=True)
    def set_resources_from_size(cls, v: Optional[VMResources], values: Dict[str, Any]) -> VMResources:
        """Set resources from size if not provided."""
        if v is not None:
            return v
        if "size" in values and values["size"] is not None:
            return VMResources.from_size(values["size"])
        return VMResources(cpu=1, memory=1, storage=10)  # Default small size

    @validator("name")
    def validate_name(cls, v: str) -> str:
        """Validate VM name."""
        if "--" in v:
            raise ValueError("VM name cannot contain consecutive hyphens")
        return v

    @validator("resources", pre=True, always=True)
    def validate_resources(cls, v: Optional[VMResources], values: Dict) -> VMResources:
        """Validate resources, using size if resources not provided."""
        if v is not None:
            return v
        if values.get("size") is not None:
            return VMResources.from_size(values["size"])
        return VMResources(cpu=1, memory=1, storage=10)  # Default small size

class VMResponse(BaseModel):
    """Response model for VM operations."""
    id: str
    name: str
    status: VMStatus
    resources: VMResources
    ip_address: Optional[str] = None
    ssh_port: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    error_message: Optional[str] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class AddSSHKeyRequest(BaseModel):
    """Request model for adding SSH key."""
    name: str = Field(..., min_length=1, max_length=64)
    public_key: str = Field(..., regex="^(ssh-rsa|ssh-ed25519) ")

class ErrorResponse(BaseModel):
    """Error response model."""
    code: str
    message: str
    details: Optional[Dict] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class ListVMsResponse(BaseModel):
    """Response model for listing VMs."""
    vms: List[VMResponse]
    total: int

class ProviderStatusResponse(BaseModel):
    """Response model for provider status."""
    status: str = "healthy"
    version: str = "0.1.0"
    resources: Dict[str, int]
    vm_count: int
    max_vms: int
