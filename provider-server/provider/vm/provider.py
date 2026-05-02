from abc import ABC, abstractmethod
from typing import Dict, List

from .models import VMConfig, VMImage, VMInfo, VMResources, VMSnapshot


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
    async def restart_vm(self, vm_id: str) -> VMInfo:
        """Restart a VM."""
        pass

    @abstractmethod
    async def suspend_vm(self, vm_id: str) -> VMInfo:
        """Suspend a VM."""
        pass

    @abstractmethod
    async def resize_vm(self, vm_id: str, resources: VMResources) -> VMInfo:
        """Resize a stopped VM."""
        pass

    @abstractmethod
    async def list_images(self) -> list[VMImage]:
        """List available VM images."""
        pass

    @abstractmethod
    async def list_snapshots(self, vm_id: str) -> list[VMSnapshot]:
        """List snapshots for a VM."""
        pass

    @abstractmethod
    async def create_snapshot(
        self, vm_id: str, name: str | None = None, comment: str | None = None
    ) -> VMSnapshot:
        """Create a snapshot for a stopped VM."""
        pass

    @abstractmethod
    async def restore_snapshot(self, vm_id: str, snapshot_name: str) -> VMInfo:
        """Restore a stopped VM from a snapshot."""
        pass

    @abstractmethod
    async def delete_snapshot(self, vm_id: str, snapshot_name: str) -> None:
        """Delete a VM snapshot."""
        pass

    @abstractmethod
    async def clone_vm(self, source_vm_id: str, destination_vm_id: str) -> VMInfo:
        """Clone a stopped VM."""
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
