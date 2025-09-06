from datetime import datetime
from typing import Dict, List

from ..discovery.resource_tracker import ResourceTracker
from ..utils.logging import setup_logger
from .models import VMConfig, VMInfo, VMResources
from .provider import VMProvider
from .name_mapper import VMNameMapper
from .cloud_init import generate_cloud_init, cleanup_cloud_init

logger = setup_logger(__name__)


class VMService:
    """Service for managing the lifecycle of VMs."""

    def __init__(
        self,
        provider: VMProvider,
        resource_tracker: ResourceTracker,
        name_mapper: VMNameMapper,
    ):
        self.provider = provider
        self.resource_tracker = resource_tracker
        self.name_mapper = name_mapper

    async def create_vm(self, config: VMConfig) -> VMInfo:
        """Create a new VM."""
        if not await self.resource_tracker.allocate(config.resources, config.name):
            raise ValueError("Insufficient resources available on provider")

        multipass_name = f"golem-{config.name}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        await self.name_mapper.add_mapping(config.name, multipass_name)

        cloud_init_path, config_id = generate_cloud_init(
            hostname=config.name,
            ssh_key=config.ssh_key
        )
        config.cloud_init_path = cloud_init_path

        try:
            vm_info = await self.provider.create_vm(config)
            return vm_info
        except Exception as e:
            logger.error(f"Failed to create VM, deallocating resources", exc_info=True)
            await self.resource_tracker.deallocate(config.resources, config.name)
            raise
        finally:
            cleanup_cloud_init(cloud_init_path, config_id)

    async def delete_vm(self, vm_id: str) -> None:
        """Delete a VM."""
        multipass_name = await self.name_mapper.get_multipass_name(vm_id)
        if not multipass_name:
            logger.warning(f"No multipass name found for VM {vm_id}")
            return

        vm_info = await self.provider.get_vm_status(multipass_name)
        await self.provider.delete_vm(multipass_name)
        await self.resource_tracker.deallocate(vm_info.resources, vm_id)
        await self.name_mapper.remove_mapping(vm_id)

    async def list_vms(self) -> List[VMInfo]:
        """List all VMs."""
        return await self.provider.list_vms()

    async def get_vm_status(self, vm_id: str) -> VMInfo:
        """Get the status of a VM."""
        multipass_name = await self.name_mapper.get_multipass_name(vm_id)
        if not multipass_name:
            from .models import VMNotFoundError
            raise VMNotFoundError(f"VM {vm_id} not found")
        return await self.provider.get_vm_status(multipass_name)

    async def get_all_vms_resources(self) -> Dict[str, VMResources]:
        """Get resources for all running VMs."""
        return await self.provider.get_all_vms_resources()
    async def initialize(self):
        await self.provider.initialize()

    async def shutdown(self):
        await self.provider.cleanup()