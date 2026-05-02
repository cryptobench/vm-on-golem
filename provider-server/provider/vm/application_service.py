import asyncio
import logging
import uuid
from typing import Any

from provider.errors import ExternalServiceError, NotFoundError
from provider.payments.stream_status_service import StreamStatusService

from .domain import CreateVMCommand, CreateVMJobResult
from .models import (
    VMAccessInfo,
    VMConfig,
    VMImage,
    VMInfo,
    VMNotFoundError,
    VMResources,
    VMSnapshot,
    VMStatus,
)
from .service import VMService

logger = logging.getLogger(__name__)


class VMApplicationService:
    """Coordinates VM lifecycle workflows across VM, payment, and job services."""

    def __init__(
        self,
        vm_service: VMService,
        settings: Any,
        stream_status_service: StreamStatusService,
        job_store: Any,
    ):
        self.vm_service = vm_service
        self.settings = settings
        self.stream_status_service = stream_status_service
        self.job_store = job_store

    def _setting(self, name: str, default: Any = None) -> Any:
        if isinstance(self.settings, dict):
            return self.settings.get(name, default)
        return getattr(self.settings, name, default)

    async def create_vm(self, command: CreateVMCommand) -> VMInfo | CreateVMJobResult:
        if await self.stream_status_service.is_payment_required():
            await self.stream_status_service.require_valid_stream(command.stream_id)

        config = VMConfig(
            name=command.name,
            image=command.image or str(self._setting("DEFAULT_VM_IMAGE", "")),
            resources=command.resources,
            ssh_key=command.ssh_key,
        )

        if command.async_mode:
            return await self._schedule_create_vm(command, config)

        try:
            vm_info = await self.vm_service.create_vm(config)
        except VMNotFoundError:
            raise
        except Exception as exc:
            logger.error(
                "VM creation failed",
                extra={"vm_id": command.name},
                exc_info=True,
            )
            raise ExternalServiceError(
                f"failed to create VM {command.name}: {exc}"
            ) from exc
        try:
            await self.stream_status_service.set_vm_stream(
                vm_info.id, command.stream_id
            )
        except Exception as exc:
            logger.error(
                "failed to persist stream mapping after VM creation",
                extra={"vm_id": vm_info.id, "stream_id": command.stream_id},
            )
            raise ExternalServiceError(
                f"failed to persist stream mapping for {vm_info.id}: {exc}"
            ) from exc
        return vm_info

    async def _schedule_create_vm(
        self, command: CreateVMCommand, config: VMConfig
    ) -> CreateVMJobResult:
        job_id = str(uuid.uuid4())
        await self.job_store.create_job(job_id, command.name, status="creating")

        async def _run_creation() -> None:
            try:
                vm_info = await self.vm_service.create_vm(config)
                await self.stream_status_service.set_vm_stream(
                    vm_info.id, command.stream_id
                )
                await self.job_store.update_job(job_id, status="ready")
            except Exception as exc:
                logger.error(
                    "Create VM job failed",
                    extra={"job_id": job_id, "vm_id": command.name},
                    exc_info=True,
                )
                await self.job_store.update_job(job_id, status="failed", error=str(exc))

        asyncio.create_task(_run_creation(), name=f"create-vm:{command.name}")
        return CreateVMJobResult(job_id=job_id, vm_id=command.name, status="creating")

    async def get_create_job(self, job_id: str) -> dict[str, Any]:
        job = await self.job_store.get_job(job_id)
        if not job:
            raise NotFoundError("job not found")
        return job

    async def list_vms(self) -> list[VMInfo]:
        try:
            return await self.vm_service.list_vms()
        except Exception as exc:
            raise ExternalServiceError(f"failed to list VMs: {exc}") from exc

    async def get_vm_status(self, vm_id: str) -> VMInfo:
        try:
            return await self.vm_service.get_vm_status(vm_id)
        except VMNotFoundError as exc:
            return await self._synthetic_creating_status(vm_id, exc)
        except Exception as exc:
            raise ExternalServiceError(
                f"failed to get VM status for {vm_id}: {exc}"
            ) from exc

    async def _synthetic_creating_status(
        self, vm_id: str, original_error: VMNotFoundError
    ) -> VMInfo:
        if not hasattr(self.vm_service, "name_mapper") or not hasattr(
            self.vm_service, "resource_tracker"
        ):
            raise original_error

        multipass_name = await self.vm_service.name_mapper.get_multipass_name(vm_id)
        if not multipass_name:
            raise original_error

        resources = self.vm_service.resource_tracker.get_allocated_resources_for(vm_id)
        if not resources:
            raise original_error

        return VMInfo(
            id=vm_id,
            name=vm_id,
            status=VMStatus.CREATING,
            resources=resources,
            ip_address=None,
            ssh_port=None,
        )

    async def get_vm_access(self, vm_id: str) -> VMAccessInfo | dict[str, Any]:
        try:
            vm = await self.vm_service.get_vm_status(vm_id)
        except VMNotFoundError:
            raise
        except Exception as exc:
            raise ExternalServiceError(
                f"failed to get VM access for {vm_id}: {exc}"
            ) from exc
        if vm is None:
            raise VMNotFoundError(f"VM {vm_id} not found")

        multipass_name = await self.vm_service.name_mapper.get_multipass_name(vm_id)
        if not multipass_name:
            raise VMNotFoundError(f"VM {vm_id} mapping not found")

        if vm.ssh_port is None:
            return {
                "vm_id": vm_id,
                "multipass_name": multipass_name,
                "status": "creating",
                "ssh_port": None,
            }

        return VMAccessInfo(
            ssh_host=str(self._setting("PUBLIC_IP", None) or "localhost"),
            ssh_port=int(vm.ssh_port),
            vm_id=vm_id,
            multipass_name=multipass_name,
        )

    async def stop_vm(self, vm_id: str) -> VMInfo:
        try:
            return await self.vm_service.stop_vm(vm_id)
        except VMNotFoundError:
            raise
        except Exception as exc:
            raise ExternalServiceError(f"failed to stop VM {vm_id}: {exc}") from exc

    async def start_vm(self, vm_id: str) -> VMInfo:
        try:
            return await self.vm_service.start_vm(vm_id)
        except VMNotFoundError:
            raise
        except Exception as exc:
            raise ExternalServiceError(f"failed to start VM {vm_id}: {exc}") from exc

    async def restart_vm(self, vm_id: str) -> VMInfo:
        try:
            return await self.vm_service.restart_vm(vm_id)
        except VMNotFoundError:
            raise
        except Exception as exc:
            raise ExternalServiceError(f"failed to restart VM {vm_id}: {exc}") from exc

    async def suspend_vm(self, vm_id: str) -> VMInfo:
        try:
            return await self.vm_service.suspend_vm(vm_id)
        except VMNotFoundError:
            raise
        except Exception as exc:
            raise ExternalServiceError(f"failed to suspend VM {vm_id}: {exc}") from exc

    async def resize_vm(self, vm_id: str, resources: VMResources) -> VMInfo:
        try:
            return await self.vm_service.resize_vm(vm_id, resources)
        except VMNotFoundError:
            raise
        except Exception as exc:
            raise ExternalServiceError(f"failed to resize VM {vm_id}: {exc}") from exc

    async def list_images(self) -> list[VMImage]:
        try:
            return await self.vm_service.list_images()
        except Exception as exc:
            raise ExternalServiceError(f"failed to list VM images: {exc}") from exc

    async def list_snapshots(self, vm_id: str) -> list[VMSnapshot]:
        try:
            return await self.vm_service.list_snapshots(vm_id)
        except VMNotFoundError:
            raise
        except Exception as exc:
            raise ExternalServiceError(
                f"failed to list snapshots for VM {vm_id}: {exc}"
            ) from exc

    async def create_snapshot(
        self, vm_id: str, name: str | None = None, comment: str | None = None
    ) -> VMSnapshot:
        try:
            return await self.vm_service.create_snapshot(vm_id, name, comment)
        except VMNotFoundError:
            raise
        except Exception as exc:
            raise ExternalServiceError(
                f"failed to create snapshot for VM {vm_id}: {exc}"
            ) from exc

    async def restore_snapshot(self, vm_id: str, snapshot_name: str) -> VMInfo:
        try:
            return await self.vm_service.restore_snapshot(vm_id, snapshot_name)
        except VMNotFoundError:
            raise
        except Exception as exc:
            raise ExternalServiceError(
                f"failed to restore snapshot {snapshot_name} for VM {vm_id}: {exc}"
            ) from exc

    async def delete_snapshot(self, vm_id: str, snapshot_name: str) -> None:
        try:
            await self.vm_service.delete_snapshot(vm_id, snapshot_name)
        except VMNotFoundError:
            raise
        except Exception as exc:
            raise ExternalServiceError(
                f"failed to delete snapshot {snapshot_name} for VM {vm_id}: {exc}"
            ) from exc

    async def clone_vm(self, source_vm_id: str, destination_vm_id: str) -> VMInfo:
        try:
            return await self.vm_service.clone_vm(source_vm_id, destination_vm_id)
        except VMNotFoundError:
            raise
        except Exception as exc:
            raise ExternalServiceError(
                f"failed to clone VM {source_vm_id}: {exc}"
            ) from exc

    async def delete_vm(self, vm_id: str) -> None:
        try:
            await self.vm_service.delete_vm(vm_id)
            await self.stream_status_service.remove_vm_stream(vm_id)
        except VMNotFoundError:
            raise
        except Exception as exc:
            raise ExternalServiceError(f"failed to delete VM {vm_id}: {exc}") from exc
