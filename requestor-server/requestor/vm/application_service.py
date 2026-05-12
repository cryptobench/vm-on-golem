import asyncio
import logging

from requestor.config import RequestorConfig
from requestor.discovery.domain import ProviderSearchQuery
from requestor.discovery.service import ProviderDiscoveryService
from requestor.errors import ConflictError, ExternalServiceError, ValidationError
from requestor.provider_client.factory import ProviderClientFactory

from .access import require_ssh_user
from .domain import (
    CloneVMCommand,
    CreateVMCommand,
    ResizeVMCommand,
    SnapshotCommand,
    VMCreateResult,
    VMRecord,
)
from .repo import VMRepository

logger = logging.getLogger(__name__)


class VMApplicationService:
    """Coordinates requestor VM workflows across discovery, provider, and storage."""

    def __init__(
        self,
        settings: RequestorConfig,
        vm_repo: VMRepository,
        discovery_service: ProviderDiscoveryService,
        provider_client_factory: ProviderClientFactory,
        payment_service=None,
    ):
        self.settings = settings
        self.vm_repo = vm_repo
        self.discovery_service = discovery_service
        self.provider_client_factory = provider_client_factory
        self.payment_service = payment_service

    def init_storage(self) -> None:
        self.vm_repo.init_schema()

    async def create_vm(self, command: CreateVMCommand) -> VMCreateResult:
        existing = self.vm_repo.get(command.name)
        if existing is not None:
            raise ConflictError(f"VM with name '{command.name}' already exists")

        provider = await self.discovery_service.require_provider(
            command.provider_id,
            ProviderSearchQuery(
                cpu=command.cpu,
                memory=command.memory,
                storage=command.storage,
            ),
        )
        resources = provider.get("resources") or {}
        if (
            int(resources.get("cpu", 0)) < command.cpu
            or int(resources.get("memory", 0)) < command.memory
            or int(resources.get("storage", 0)) < command.storage
        ):
            raise ValidationError("Provider does not have enough resources available")

        provider_ip = (
            "localhost"
            if self.settings.environment == "development"
            else provider.get("ip_address")
        )
        if not provider_ip:
            raise ValidationError("Provider IP address not found in advertisement")

        async with self.provider_client_factory.for_provider_ip(provider_ip) as client:
            try:
                job = await client.create_vm(
                    name=command.name,
                    cpu=command.cpu,
                    memory=command.memory,
                    storage=command.storage,
                    ssh_key=command.ssh_key,
                    stream_id=command.stream_id,
                )
                vm_id = job.get("vm_id") or command.name
                self.vm_repo.save(
                    name=command.name,
                    provider_ip=provider_ip,
                    vm_id=vm_id,
                    config={
                        "cpu": command.cpu,
                        "memory": command.memory,
                        "storage": command.storage,
                        **(
                            {"stream_id": command.stream_id}
                            if command.stream_id is not None
                            else {}
                        ),
                    },
                    status="creating",
                )
                access = await self._wait_for_access(client, vm_id)
            except Exception as exc:
                logger.error("provider VM creation failed", exc_info=True)
                raise ExternalServiceError(
                    f"failed to create VM on provider {command.provider_id}: {exc}"
                ) from exc

        config = {
            "cpu": command.cpu,
            "memory": command.memory,
            "storage": command.storage,
            "ssh_port": access.get("ssh_port"),
            "ssh_user": require_ssh_user(access),
            **(
                {"stream_id": command.stream_id}
                if command.stream_id is not None
                else {}
            ),
        }
        self.vm_repo.update_status(command.name, "running")
        record = self.vm_repo.require(command.name)
        # Preserve the provider-returned ID and access config.
        self.vm_repo.delete(command.name)
        self.vm_repo.save(
            name=command.name,
            provider_ip=provider_ip,
            vm_id=access.get("vm_id") or record.vm_id,
            config=config,
            status="running",
        )
        return VMCreateResult(
            name=command.name,
            provider_ip=provider_ip,
            vm_id=access.get("vm_id") or record.vm_id,
            config=config,
            status="running",
        )

    async def _wait_for_access(self, client, vm_id: str) -> dict:
        deadline = asyncio.get_running_loop().time() + 600.0
        last_status = "creating"
        while asyncio.get_running_loop().time() < deadline:
            info = await client.get_vm_info(vm_id)
            last_status = (info.get("status") or last_status).lower()
            if last_status == "running":
                return await client.get_vm_access(vm_id)
            await asyncio.sleep(2.0)
        raise ExternalServiceError(
            f"VM did not become ready in time (status={last_status})"
        )

    async def list_vms(self) -> list[VMRecord]:
        return self.vm_repo.list()

    async def get_vm(self, name: str) -> VMRecord:
        vm = self.vm_repo.require(name)
        return await self._ensure_ssh_user(vm)

    async def _ensure_ssh_user(self, vm: VMRecord) -> VMRecord:
        if vm.config.get("ssh_user"):
            return vm

        async with self.provider_client_factory.for_provider_ip(
            vm.provider_ip
        ) as client:
            access = await client.get_vm_access(vm.vm_id)

        config = {
            **vm.config,
            "ssh_user": require_ssh_user(access),
            **(
                {"ssh_port": access.get("ssh_port")}
                if access.get("ssh_port") is not None
                else {}
            ),
        }
        self.vm_repo.update_config(vm.name, config, status=vm.status)
        return self.vm_repo.require(vm.name)

    async def start_vm(self, name: str) -> VMRecord:
        vm = self.vm_repo.require(name)
        async with self.provider_client_factory.for_provider_ip(
            vm.provider_ip
        ) as client:
            await client.start_vm(vm.vm_id)
        self.vm_repo.update_status(name, "running")
        return self.vm_repo.require(name)

    async def stop_vm(self, name: str) -> VMRecord:
        vm = self.vm_repo.require(name)
        async with self.provider_client_factory.for_provider_ip(
            vm.provider_ip
        ) as client:
            await client.stop_vm(vm.vm_id)
        self.vm_repo.update_status(name, "stopped")
        return self.vm_repo.require(name)

    async def restart_vm(self, name: str) -> VMRecord:
        vm = self.vm_repo.require(name)
        async with self.provider_client_factory.for_provider_ip(
            vm.provider_ip
        ) as client:
            result = await client.restart_vm(vm.vm_id)
        self._sync_record(name, result)
        return self.vm_repo.require(name)

    async def suspend_vm(self, name: str) -> VMRecord:
        vm = self.vm_repo.require(name)
        async with self.provider_client_factory.for_provider_ip(
            vm.provider_ip
        ) as client:
            result = await client.suspend_vm(vm.vm_id)
        self._sync_record(name, result, fallback_status="suspended")
        return self.vm_repo.require(name)

    async def resume_vm(self, name: str) -> VMRecord:
        vm = self.vm_repo.require(name)
        async with self.provider_client_factory.for_provider_ip(
            vm.provider_ip
        ) as client:
            result = await client.resume_vm(vm.vm_id)
        self._sync_record(name, result, fallback_status="running")
        return self.vm_repo.require(name)

    async def resize_vm(self, name: str, command: ResizeVMCommand) -> VMRecord:
        vm = self.vm_repo.require(name)
        if vm.config.get("stream_id") is not None and command.stream_id is None:
            raise ValidationError("resizing a paid VM requires a replacement stream")
        async with self.provider_client_factory.for_provider_ip(
            vm.provider_ip
        ) as client:
            result = await client.resize_vm(
                vm.vm_id, command.cpu, command.memory, command.storage
            )
        config = {
            **vm.config,
            "cpu": command.cpu,
            "memory": command.memory,
            "storage": command.storage,
            **(
                {"stream_id": command.stream_id}
                if command.stream_id is not None
                else {}
            ),
        }
        self.vm_repo.update_config(
            name, config, status=str(result.get("status") or vm.status)
        )
        return self.vm_repo.require(name)

    async def list_provider_images(self, provider_id: str) -> list[dict]:
        provider = await self.discovery_service.require_provider(
            provider_id, ProviderSearchQuery()
        )
        provider_ip = (
            "localhost"
            if self.settings.environment == "development"
            else provider.get("ip_address")
        )
        if not provider_ip:
            raise ValidationError("Provider IP address not found in advertisement")
        async with self.provider_client_factory.for_provider_ip(provider_ip) as client:
            return await client.list_images()

    async def list_snapshots(self, name: str) -> list[dict]:
        vm = self.vm_repo.require(name)
        async with self.provider_client_factory.for_provider_ip(
            vm.provider_ip
        ) as client:
            return await client.list_snapshots(vm.vm_id)

    async def create_snapshot(self, name: str, command: SnapshotCommand) -> dict:
        vm = self.vm_repo.require(name)
        async with self.provider_client_factory.for_provider_ip(
            vm.provider_ip
        ) as client:
            return await client.create_snapshot(vm.vm_id, command.name, command.comment)

    async def restore_snapshot(self, name: str, snapshot_name: str) -> VMRecord:
        vm = self.vm_repo.require(name)
        async with self.provider_client_factory.for_provider_ip(
            vm.provider_ip
        ) as client:
            result = await client.restore_snapshot(vm.vm_id, snapshot_name)
        self._sync_record(name, result)
        return self.vm_repo.require(name)

    async def delete_snapshot(self, name: str, snapshot_name: str) -> None:
        vm = self.vm_repo.require(name)
        async with self.provider_client_factory.for_provider_ip(
            vm.provider_ip
        ) as client:
            await client.delete_snapshot(vm.vm_id, snapshot_name)

    async def clone_vm(self, source_name: str, command: CloneVMCommand) -> VMRecord:
        source = self.vm_repo.require(source_name)
        if self.vm_repo.get(command.name) is not None:
            raise ConflictError(f"VM with name '{command.name}' already exists")
        if source.config.get("stream_id") is not None and command.stream_id is None:
            raise ValidationError("cloning a paid VM requires a replacement stream")
        async with self.provider_client_factory.for_provider_ip(
            source.provider_ip
        ) as client:
            result = await client.clone_vm(source.vm_id, command.name)
        config = {
            **source.config,
            **(
                {"stream_id": command.stream_id}
                if command.stream_id is not None
                else {}
            ),
        }
        self.vm_repo.save(
            name=command.name,
            provider_ip=source.provider_ip,
            vm_id=result.get("id") or command.name,
            config=config,
            status=str(result.get("status") or "stopped"),
        )
        return self.vm_repo.require(command.name)

    async def delete_vm(self, name: str) -> None:
        vm = self.vm_repo.require(name)
        await self._terminate_stream_for_delete(vm)
        async with self.provider_client_factory.for_provider_ip(
            vm.provider_ip
        ) as client:
            await client.destroy_vm(vm.vm_id)
        self.vm_repo.delete(name)

    async def _terminate_stream_for_delete(self, vm: VMRecord) -> None:
        stream_id = vm.config.get("stream_id")
        if stream_id is None:
            return
        if self.payment_service is None:
            raise ExternalServiceError(
                "payment service unavailable for stream termination"
            )
        try:
            await self.payment_service.terminate_stream(int(stream_id))
        except ExternalServiceError as exc:
            if "no-stream" in str(exc).lower():
                return
            raise

    def _sync_record(
        self, name: str, result: dict, fallback_status: str | None = None
    ) -> None:
        current = self.vm_repo.require(name)
        resources = result.get("resources") or {}
        config = {
            **current.config,
            **(
                {
                    "cpu": resources.get("cpu"),
                    "memory": resources.get("memory"),
                    "storage": resources.get("storage"),
                }
                if resources
                else {}
            ),
            **(
                {"ssh_port": result.get("ssh_port")}
                if result.get("ssh_port") is not None
                else {}
            ),
            **(
                {"ssh_user": require_ssh_user(result)}
                if result.get("ssh_user") is not None
                else {}
            ),
        }
        self.vm_repo.update_config(
            name,
            config,
            status=str(result.get("status") or fallback_status or current.status),
        )
