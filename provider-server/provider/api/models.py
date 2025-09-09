from pydantic import BaseModel, Field, field_validator
from typing import Dict, Optional, List, Any
from datetime import datetime

from ..utils.logging import setup_logger
from ..vm.models import VMSize, VMResources, VMStatus

logger = setup_logger(__name__)


class CreateVMRequest(BaseModel):
    """Request model for creating a VM."""
    name: str = Field(..., min_length=3, max_length=64,
                      pattern="^[a-z0-9][a-z0-9-]*[a-z0-9]$")
    size: Optional[VMSize] = None
    resources: Optional[VMResources] = None
    image: str = Field(default="24.04")  # Ubuntu 24.04 LTS
    ssh_key: str = Field(..., pattern="^(ssh-rsa|ssh-ed25519) ",
                         description="SSH public key for VM access")
    stream_id: Optional[int] = Field(
        default=None,
        description="On-chain StreamPayment stream id used to fund this VM"
    )

    @field_validator("name")
    def validate_name(cls, v: str) -> str:
        """Validate VM name."""
        if "--" in v:
            raise ValueError("VM name cannot contain consecutive hyphens")
        return v

    @field_validator("resources", mode='before')
    def validate_resources(cls, v: Optional[Dict[str, Any]], values: Dict[str, Any]) -> VMResources:
        """Validate and set resources."""
        logger.debug(f"Validating resources input: {v}")

        try:
            # If resources directly provided as dict
            if isinstance(v, dict):
                result = VMResources(**v)
                logger.debug(f"Created resources from dict: {result}")
                return result

            # If VMResources instance provided
            if isinstance(v, VMResources):
                logger.debug(f"Using provided VMResources: {v}")
                return v

            # If size provided, use that
            if "size" in values.data and values.data["size"] is not None:
                result = VMResources.from_size(values.data["size"])
                logger.debug(
                    f"Created resources from size {values.data['size']}: {result}")
                return result

            # Only use defaults if nothing provided
            result = VMResources(cpu=1, memory=1, storage=10)
            logger.debug(f"Using default resources: {result}")
            return result

        except Exception as e:
            logger.error(f"Error validating resources: {e}")
            logger.error(f"Input value: {v}")
            logger.error(f"Values dict: {values.data}")
            raise ValueError(f"Invalid resource configuration: {str(e)}")


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
    public_key: str = Field(..., pattern="^(ssh-rsa|ssh-ed25519) ")


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


class ProviderInfoResponse(BaseModel):
    provider_id: str
    stream_payment_address: str
    glm_token_address: str


class StreamOnChain(BaseModel):
    token: str
    sender: str
    recipient: str
    startTime: int
    stopTime: int
    ratePerSecond: int
    deposit: int
    withdrawn: int
    halted: bool


class StreamComputed(BaseModel):
    now: int
    remaining_seconds: int
    vested_wei: int
    withdrawable_wei: int


class StreamStatus(BaseModel):
    vm_id: str
    stream_id: int
    chain: StreamOnChain
    computed: StreamComputed
    verified: bool
    reason: str
