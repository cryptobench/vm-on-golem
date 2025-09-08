from datetime import datetime
from typing import Dict, List

from ..discovery.resource_tracker import ResourceTracker
from ..utils.logging import setup_logger
from .models import VMConfig, VMInfo, VMResources, VMNotFoundError
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
        blockchain_client: object | None = None,
    ):
        self.provider = provider
        self.resource_tracker = resource_tracker
        self.name_mapper = name_mapper
        self.blockchain_client = blockchain_client

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

        try:
            vm_info = await self.provider.get_vm_status(multipass_name)
            await self.provider.delete_vm(multipass_name)
            await self.resource_tracker.deallocate(vm_info.resources, vm_id)
            # Optional: best-effort on-chain termination if we have a mapping
            try:
                if self.blockchain_client:
                    # In future: look up stream id associated to this vm_id
                    pass
            except Exception:
                pass
        except VMNotFoundError:
            logger.warning(f"VM {multipass_name} not found on provider, cleaning up resources")
            # If the VM is not found, we still need to deallocate the resources we have tracked for it
            # Since we can't get the resources from the provider, we'll have to assume the resources are what we have tracked
            # This is not ideal, but it's the best we can do in this situation
            # A better solution would be to store the resources in the name mapper
            pass
        finally:
            await self.name_mapper.remove_mapping(vm_id)

    async def stop_vm(self, vm_id: str) -> VMInfo:
        """Stop a VM and return its updated status."""
        multipass_name = await self.name_mapper.get_multipass_name(vm_id)
        if not multipass_name:
            raise VMNotFoundError(f"VM {vm_id} not found")
        vm = await self.provider.stop_vm(multipass_name)
        # Optional: best-effort withdraw for active stream
        try:
            if self.blockchain_client:
                # In future: look up stream id associated to this vm_id
                pass
        except Exception:
            pass
        return vm
 
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
