from datetime import datetime
from enum import Enum
from typing import Dict, Optional

from pydantic import BaseModel, Field, field_validator


class VMStatus(str, Enum):
    """VM status enum."""

    CREATING = "creating"
    STARTING = "starting"
    RESTARTING = "restarting"
    RUNNING = "running"
    DELAYED_SHUTDOWN = "delayed_shutdown"
    SUSPENDING = "suspending"
    SUSPENDED = "suspended"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"
    DELETED = "deleted"
    UNKNOWN = "unknown"

    @classmethod
    def from_multipass(cls, state: str | None) -> "VMStatus":
        """Map raw Multipass states to VMStatus, defaulting to UNKNOWN."""

        if state is None:
            return cls.UNKNOWN

        normalized = state.strip().lower().replace("-", "_").replace(" ", "_")
        mapping = {
            "creating": cls.CREATING,
            "starting": cls.STARTING,
            "restarting": cls.RESTARTING,
            "running": cls.RUNNING,
            "delayed_shutdown": cls.DELAYED_SHUTDOWN,
            "suspending": cls.SUSPENDING,
            "suspended": cls.SUSPENDED,
            "stopping": cls.STOPPING,
            "stopped": cls.STOPPED,
            "error": cls.ERROR,
            "deleted": cls.DELETED,
            "unknown": cls.UNKNOWN,
        }
        return mapping.get(normalized, cls.UNKNOWN)


class VMSize(str, Enum):
    """Predefined VM sizes."""

    SMALL = "small"  # 1 CPU, 1GB RAM, 10GB storage
    MEDIUM = "medium"  # 2 CPU, 4GB RAM, 20GB storage
    LARGE = "large"  # 4 CPU, 8GB RAM, 40GB storage
    XLARGE = "xlarge"  # 8 CPU, 16GB RAM, 80GB storage


class VMResources(BaseModel):
    """VM resource configuration."""

    cpu: int = Field(..., ge=1, description="Number of CPU cores")
    memory: int = Field(..., ge=1, description="Memory in GB")
    storage: int = Field(..., ge=10, description="Storage in GB")

    @field_validator("cpu")
    def validate_cpu(cls, v: int) -> int:
        """Validate CPU cores."""
        if v not in [1, 2, 4, 8, 16]:
            raise ValueError("CPU cores must be 1, 2, 4, 8, or 16")
        return v

    @field_validator("memory")
    def validate_memory(cls, v: int) -> int:
        """Validate memory."""
        if v not in [1, 2, 4, 8, 16, 32, 64]:
            raise ValueError("Memory must be 1, 2, 4, 8, 16, 32, or 64 GB")
        return v

    @classmethod
    def from_size(cls, size: VMSize) -> "VMResources":
        """Create resources from predefined size."""
        sizes = {
            VMSize.SMALL: {"cpu": 1, "memory": 1, "storage": 10},
            VMSize.MEDIUM: {"cpu": 2, "memory": 4, "storage": 20},
            VMSize.LARGE: {"cpu": 4, "memory": 8, "storage": 40},
            VMSize.XLARGE: {"cpu": 8, "memory": 16, "storage": 80},
        }
        return cls(**sizes[size])


class VMCreateRequest(BaseModel):
    """Request to create a new VM."""

    name: str = Field(
        ..., min_length=3, max_length=64, pattern="^[a-z0-9][a-z0-9-]*[a-z0-9]$"
    )
    size: Optional[VMSize] = None
    cpu_cores: Optional[int] = None
    memory_gb: Optional[int] = None
    storage_gb: Optional[int] = None
    image: Optional[str] = Field(default="24.04")  # Ubuntu 24.04 LTS
    ssh_key: str = Field(
        ...,
        pattern="^(ssh-rsa|ssh-ed25519) ",
        description="SSH public key for VM access",
    )

    @field_validator("name")
    def validate_name(cls, v: str) -> str:
        """Validate VM name."""
        if "--" in v:
            raise ValueError("VM name cannot contain consecutive hyphens")
        return v

    @field_validator("cpu_cores")
    def validate_cpu(cls, v: Optional[int]) -> Optional[int]:
        """Validate CPU cores."""
        if v is not None and v not in [1, 2, 4, 8, 16]:
            raise ValueError("CPU cores must be 1, 2, 4, 8, or 16")
        return v

    @field_validator("memory_gb")
    def validate_memory(cls, v: Optional[int]) -> Optional[int]:
        """Validate memory."""
        if v is not None and v not in [1, 2, 4, 8, 16, 32, 64]:
            raise ValueError("Memory must be 1, 2, 4, 8, 16, 32, or 64 GB")
        return v


class VMConfig(BaseModel):
    """VM configuration."""

    name: str = Field(
        ..., min_length=3, max_length=64, pattern="^[a-z0-9][a-z0-9-]*[a-z0-9]$"
    )
    resources: VMResources
    image: str = Field(default="24.04")  # Ubuntu 24.04 LTS
    size: Optional[VMSize] = None
    ssh_key: str = Field(
        ...,
        pattern="^(ssh-rsa|ssh-ed25519) ",
        description="SSH public key for VM access",
    )
    cloud_init_path: Optional[str] = None
    # Final multipass VM name to use; if None, provider may generate one.
    multipass_name: Optional[str] = None

    @field_validator("name")
    def validate_name(cls, v: str) -> str:
        """Validate VM name."""
        if "--" in v:
            raise ValueError("VM name cannot contain consecutive hyphens")
        return v


class VMInfo(BaseModel):
    """VM information."""

    id: str
    name: str
    status: VMStatus
    resources: VMResources
    ip_address: Optional[str] = None
    ssh_port: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    error_message: Optional[str] = None

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class VMImage(BaseModel):
    """Available VM image entry."""

    alias: str
    version: Optional[str] = None
    description: Optional[str] = None


class VMSnapshot(BaseModel):
    """Snapshot metadata for a VM."""

    name: str
    vm_id: str
    comment: Optional[str] = None
    created_at: Optional[str] = None


class ResizeVMRequest(BaseModel):
    """Request to resize an existing VM."""

    resources: VMResources


class CreateSnapshotRequest(BaseModel):
    """Request to create a VM snapshot."""

    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=64,
        pattern="^[a-z0-9][a-z0-9-]*[a-z0-9]$",
    )
    comment: Optional[str] = Field(default=None, max_length=256)


class CloneVMRequest(BaseModel):
    """Request to clone a stopped VM."""

    name: str = Field(
        ..., min_length=3, max_length=64, pattern="^[a-z0-9][a-z0-9-]*[a-z0-9]$"
    )


class SSHKey(BaseModel):
    """SSH key information."""

    name: str = Field(..., min_length=1, max_length=64)
    public_key: str = Field(..., pattern="^(ssh-rsa|ssh-ed25519) ")
    fingerprint: Optional[str] = None


class VMAccessInfo(BaseModel):
    """VM access information."""

    ssh_host: str
    ssh_port: int
    vm_id: str = Field(..., description="Requestor's VM name")
    multipass_name: str = Field(
        ..., description="Full multipass VM name with timestamp"
    )


class VMProvider:
    """Base interface for VM providers."""

    async def initialize(self) -> None:
        """Initialize the provider."""
        raise NotImplementedError()

    async def cleanup(self) -> None:
        """Cleanup provider resources."""
        raise NotImplementedError()

    async def create_vm(self, config: VMConfig) -> VMInfo:
        """Create a new VM."""
        raise NotImplementedError()

    async def delete_vm(self, vm_id: str) -> None:
        """Delete a VM."""
        raise NotImplementedError()

    async def start_vm(self, vm_id: str) -> VMInfo:
        """Start a VM."""
        raise NotImplementedError()

    async def stop_vm(self, vm_id: str) -> VMInfo:
        """Stop a VM."""
        raise NotImplementedError()

    async def get_vm_status(self, vm_id: str) -> VMInfo:
        """Get VM status."""
        raise NotImplementedError()

    async def add_ssh_key(self, vm_id: str, key: SSHKey) -> None:
        """Add SSH key to VM."""
        raise NotImplementedError()


class VMError(Exception):
    """Base class for VM errors."""

    def __init__(self, message: str, vm_id: Optional[str] = None):
        self.message = message
        self.vm_id = vm_id
        super().__init__(message)


class VMCreateError(VMError):
    """Error creating VM."""

    pass


class VMNotFoundError(VMError):
    """VM not found."""

    pass


class VMStateError(VMError):
    """Invalid VM state for operation."""

    pass


class ResourceError(VMError):
    """Resource allocation error."""

    pass
