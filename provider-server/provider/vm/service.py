from datetime import datetime
from typing import Dict, List

from provider.errors import ConflictError, ValidationError

from ..discovery.resource_tracker import ResourceTracker
from ..utils.logging import setup_logger
from .cloud_init import cleanup_cloud_init, generate_cloud_init
from .lifecycle import ProgressCallback, creation_lifecycle
from .models import (
    VMConfig,
    VMImage,
    VMInfo,
    VMNotFoundError,
    VMResources,
    VMSnapshot,
    VMStatus,
)
from .name_mapper import VMNameMapper
from .provider import VMProvider

logger = setup_logger(__name__)


class VMService:
    """Service for managing the lifecycle of VMs."""

    def __init__(
        self,
        provider: VMProvider,
        resource_tracker: ResourceTracker,
        name_mapper: VMNameMapper,
        monitoring_repo: object | None = None,
        blockchain_client: object | None = None,
    ):
        self.provider = provider
        self.resource_tracker = resource_tracker
        self.name_mapper = name_mapper
        self.monitoring_repo = monitoring_repo
        self.blockchain_client = blockchain_client

    async def create_vm(self, config: VMConfig) -> VMInfo:
        """Create a new VM."""
        return await self.create_vm_with_progress(config)

    async def create_vm_with_progress(
        self,
        config: VMConfig,
        progress_callback: ProgressCallback | None = None,
    ) -> VMInfo:
        """Create a new VM and optionally report lifecycle progress."""
        await self._report_progress(
            progress_callback,
            "allocating_resources",
            "Reserving provider resources",
            10,
        )
        if not await self.resource_tracker.allocate(config.resources, config.name):
            raise ValueError("Insufficient resources available on provider")

        # Generate a stable multipass name up-front so downstream code and
        # status checks see a consistent mapping during provisioning.
        from uuid import uuid4

        multipass_name = f"golem-{uuid4()}"
        config.multipass_name = multipass_name
        await self.name_mapper.add_mapping(config.name, multipass_name)
        await self._report_progress(
            progress_callback,
            "preparing_guest",
            "Preparing guest configuration",
            20,
        )

        monitoring_token = None
        if self.monitoring_repo is not None:
            self.monitoring_repo.init_schema()
            monitoring_token = self.monitoring_repo.issue_guest_token(config.name)

        cloud_init_path, config_id = generate_cloud_init(
            hostname=config.name,
            ssh_key=config.ssh_key,
            monitoring_vm_id=config.name,
            monitoring_token=monitoring_token,
        )
        config.cloud_init_path = cloud_init_path

        try:
            vm_info = await self.provider.create_vm(config, progress_callback)
            return vm_info
        except Exception as e:
            logger.error(f"Failed to create VM, deallocating resources", exc_info=True)
            await self.resource_tracker.deallocate(config.resources, config.name)
            if self.monitoring_repo is not None:
                self.monitoring_repo.delete_guest_token(config.name)
            raise
        finally:
            cleanup_cloud_init(cloud_init_path, config_id)

    @staticmethod
    async def _report_progress(
        progress_callback: ProgressCallback | None,
        stage: str,
        message: str,
        progress: int,
    ) -> None:
        if progress_callback is None:
            return
        await progress_callback(creation_lifecycle(stage, message, progress))

    async def delete_vm(self, vm_id: str) -> None:
        """Delete a VM."""
        multipass_name = await self.name_mapper.get_multipass_name(vm_id)
        if not multipass_name:
            raise VMNotFoundError(f"VM {vm_id} not found")

        try:
            vm_info = await self.provider.get_vm_status(multipass_name)
            logger.info(
                f"Deleting VM {vm_id} (multipass={multipass_name}) with status={vm_info.status}"
            )
            await self.provider.delete_vm(multipass_name)
            await self.resource_tracker.deallocate(vm_info.resources, vm_id)
            if self.monitoring_repo is not None:
                self.monitoring_repo.delete_guest_token(vm_id)
            # Optional: best-effort on-chain termination if we have a mapping
            try:
                if self.blockchain_client:
                    # In future: look up stream id associated to this vm_id
                    pass
            except Exception:
                pass
        except VMNotFoundError as exc:
            logger.error(
                "VM mapped but not found on provider during delete",
                extra={"vm_id": vm_id, "multipass_name": multipass_name},
            )
            raise exc
        finally:
            await self.name_mapper.remove_mapping(vm_id)

    async def start_vm(self, vm_id: str) -> VMInfo:
        """Start a VM and return its updated status."""
        multipass_name = await self._require_multipass_name(vm_id)
        logger.info(f"Starting VM {vm_id} (multipass={multipass_name})")
        return await self.provider.start_vm(multipass_name)

    async def stop_vm(self, vm_id: str) -> VMInfo:
        """Stop a VM and return its updated status."""
        multipass_name = await self._require_multipass_name(vm_id)
        logger.info(f"Stopping VM {vm_id} (multipass={multipass_name})")
        vm = await self.provider.stop_vm(multipass_name)
        logger.info(f"Stopped VM {vm_id} result status={getattr(vm, 'status', '?')}")
        # Optional: best-effort withdraw for active stream
        try:
            if self.blockchain_client:
                # In future: look up stream id associated to this vm_id
                pass
        except Exception:
            pass
        return vm

    async def restart_vm(self, vm_id: str) -> VMInfo:
        """Restart a VM and return its updated status."""
        multipass_name = await self._require_multipass_name(vm_id)
        logger.info(f"Restarting VM {vm_id} (multipass={multipass_name})")
        return await self.provider.restart_vm(multipass_name)

    async def suspend_vm(self, vm_id: str) -> VMInfo:
        """Suspend a VM and return its updated status."""
        multipass_name = await self._require_multipass_name(vm_id)
        logger.info(f"Suspending VM {vm_id} (multipass={multipass_name})")
        return await self.provider.suspend_vm(multipass_name)

    async def resize_vm(self, vm_id: str, resources: VMResources) -> VMInfo:
        """Resize a VM and update reserved capacity."""
        multipass_name = await self._require_multipass_name(vm_id)
        current = await self.provider.get_vm_status(multipass_name)
        restart_after_resize = current.status == VMStatus.RUNNING
        if current.status not in {VMStatus.RUNNING, VMStatus.STOPPED}:
            raise ConflictError("VM must be running or stopped before resize")
        if resources.storage < current.resources.storage:
            raise ValidationError("storage can only be increased")

        if restart_after_resize:
            await self.provider.stop_vm(multipass_name)

        if not await self.resource_tracker.resize(vm_id, resources):
            if restart_after_resize:
                await self._restart_after_failed_resize(vm_id, multipass_name)
            raise ValueError("Insufficient resources available on provider")

        try:
            resized = await self.provider.resize_vm(multipass_name, resources)
        except Exception:
            await self.resource_tracker.resize(vm_id, current.resources)
            if restart_after_resize:
                await self._restart_after_failed_resize(vm_id, multipass_name)
            raise

        if not restart_after_resize:
            return resized

        try:
            return await self.provider.start_vm(multipass_name)
        except Exception:
            logger.error(
                "VM resize succeeded but restart failed",
                extra={"vm_id": vm_id, "multipass_name": multipass_name},
                exc_info=True,
            )
            raise

    async def _restart_after_failed_resize(
        self, vm_id: str, multipass_name: str
    ) -> None:
        try:
            await self.provider.start_vm(multipass_name)
        except Exception:
            logger.error(
                "Failed to restart VM after resize did not complete",
                extra={"vm_id": vm_id, "multipass_name": multipass_name},
                exc_info=True,
            )
            raise

    async def list_images(self) -> list[VMImage]:
        """List available VM images."""
        return await self.provider.list_images()

    async def list_snapshots(self, vm_id: str) -> list[VMSnapshot]:
        """List snapshots for a VM."""
        multipass_name = await self._require_multipass_name(vm_id)
        return await self.provider.list_snapshots(multipass_name)

    async def create_snapshot(
        self, vm_id: str, name: str | None = None, comment: str | None = None
    ) -> VMSnapshot:
        """Create a snapshot for a stopped VM."""
        multipass_name = await self._require_multipass_name(vm_id)
        current = await self.provider.get_vm_status(multipass_name)
        self._require_stopped(current, "snapshot")
        return await self.provider.create_snapshot(multipass_name, name, comment)

    async def restore_snapshot(self, vm_id: str, snapshot_name: str) -> VMInfo:
        """Restore a stopped VM from a snapshot."""
        multipass_name = await self._require_multipass_name(vm_id)
        current = await self.provider.get_vm_status(multipass_name)
        self._require_stopped(current, "restore snapshot")
        return await self.provider.restore_snapshot(multipass_name, snapshot_name)

    async def delete_snapshot(self, vm_id: str, snapshot_name: str) -> None:
        """Delete a VM snapshot."""
        multipass_name = await self._require_multipass_name(vm_id)
        await self.provider.delete_snapshot(multipass_name, snapshot_name)

    async def clone_vm(self, source_vm_id: str, destination_vm_id: str) -> VMInfo:
        """Clone a stopped VM under a new requestor-facing name."""
        if await self.name_mapper.get_multipass_name(destination_vm_id):
            raise ConflictError(f"VM {destination_vm_id} already exists")

        source_multipass_name = await self._require_multipass_name(source_vm_id)
        source = await self.provider.get_vm_status(source_multipass_name)
        self._require_stopped(source, "clone")
        if not await self.resource_tracker.allocate(
            source.resources, destination_vm_id
        ):
            raise ValueError("Insufficient resources available on provider")

        from uuid import uuid4

        destination_multipass_name = f"golem-{uuid4()}"
        await self.name_mapper.add_mapping(
            destination_vm_id, destination_multipass_name
        )
        try:
            return await self.provider.clone_vm(
                source_multipass_name, destination_multipass_name
            )
        except Exception:
            await self.resource_tracker.deallocate(source.resources, destination_vm_id)
            await self.name_mapper.remove_mapping(destination_vm_id)
            raise

    async def list_vms(self) -> List[VMInfo]:
        """List all VMs."""
        return await self.provider.list_vms()

    async def get_vm_status(self, vm_id: str) -> VMInfo:
        """Get the status of a VM."""
        multipass_name = await self._require_multipass_name(vm_id)
        return await self.provider.get_vm_status(multipass_name)

    async def get_all_vms_resources(self) -> Dict[str, VMResources]:
        """Get resources for all running VMs."""
        return await self.provider.get_all_vms_resources()

    async def initialize(self):
        await self.provider.initialize()

    async def shutdown(self):
        await self.provider.cleanup()

    async def _require_multipass_name(self, vm_id: str) -> str:
        multipass_name = await self.name_mapper.get_multipass_name(vm_id)
        if not multipass_name:
            raise VMNotFoundError(f"VM {vm_id} not found")
        return multipass_name

    @staticmethod
    def _require_stopped(vm: VMInfo, action: str) -> None:
        if vm.status != VMStatus.STOPPED:
            raise ConflictError(f"VM must be stopped before {action}")
