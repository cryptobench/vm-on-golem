import asyncio
import logging

from requestor.config import RequestorConfig
from requestor.discovery.domain import ProviderSearchQuery
from requestor.discovery.service import ProviderDiscoveryService
from requestor.errors import ConflictError, ExternalServiceError, ValidationError
from requestor.provider_client.factory import ProviderClientFactory

from .domain import CreateVMCommand, VMCreateResult, VMRecord
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
    ):
        self.settings = settings
        self.vm_repo = vm_repo
        self.discovery_service = discovery_service
        self.provider_client_factory = provider_client_factory

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
        return self.vm_repo.require(name)

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

    async def delete_vm(self, name: str) -> None:
        vm = self.vm_repo.require(name)
        async with self.provider_client_factory.for_provider_ip(
            vm.provider_ip
        ) as client:
            await client.destroy_vm(vm.vm_id)
        self.vm_repo.delete(name)
