from abc import ABC, abstractmethod
from typing import Dict, List

from .models import VMConfig, VMInfo, VMResources


class VMProvider(ABC):
    """Abstract base class for VM providers."""

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the VM provider."""
        pass

    @abstractmethod
    async def create_vm(self, config: VMConfig) -> VMInfo:
        """Create a new VM."""
        pass

    @abstractmethod
    async def delete_vm(self, vm_id: str) -> None:
        """Delete a VM."""
        pass

    @abstractmethod
    async def start_vm(self, vm_id: str) -> VMInfo:
        """Start a VM."""
        pass

    @abstractmethod
    async def stop_vm(self, vm_id: str) -> VMInfo:
        """Stop a VM."""
        pass

    @abstractmethod
    async def get_vm_status(self, vm_id: str) -> VMInfo:
        """Get the status of a VM."""
        pass

    @abstractmethod
    def get_all_vms_resources(self) -> Dict[str, VMResources]:
        """Get resources for all running VMs."""
        pass

    @abstractmethod
    async def cleanup(self) -> None:
        """Cleanup resources used by the provider."""
        pass
