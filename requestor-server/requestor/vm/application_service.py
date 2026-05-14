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
        logger.info(
            "Requestor VM create requested",
            extra={
                "vm_name": command.name,
                "provider_id": command.provider_id,
                "cpu": command.cpu,
                "memory": command.memory,
                "storage": command.storage,
            },
        )
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
            logger.warning(
                "Provider does not have enough resources for VM create",
                extra={"vm_name": command.name, "provider_id": command.provider_id},
            )
            raise ValidationError("Provider does not have enough resources available")

        provider_ip = (
            "localhost"
            if self.settings.environment == "development"
            else provider.get("ip_address")
        )
        if not provider_ip:
            logger.warning(
                "Provider advertisement missing IP address",
                extra={"provider_id": command.provider_id},
            )
            raise ValidationError("Provider IP address not found in advertisement")
        provider_endpoint_url = self._require_provider_endpoint(
            provider, command.provider_id
        )
        logger.info(
            "Selected provider for VM create",
            extra={
                "vm_name": command.name,
                "provider_id": command.provider_id,
                "provider_endpoint_url": provider_endpoint_url,
            },
        )

        async with self.provider_client_factory.for_provider_endpoint(
            provider_endpoint_url
        ) as client:
            try:
                job = await client.create_vm(
                    name=command.name,
                    cpu=command.cpu,
                    memory=command.memory,
                    storage=command.storage,
                    ssh_key=command.ssh_key,
                    stream_id=command.stream_id,
                )
                logger.info(
                    "Provider accepted VM create request",
                    extra={"vm_name": command.name, "job_id": job.get("job_id")},
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
                        **(
                            {"provider_endpoint_url": provider_endpoint_url}
                        ),
                    },
                    status="creating",
                )
                logger.info(
                    "Saved local VM creation record",
                    extra={"vm_name": command.name, "vm_id": vm_id},
                )
                access = await self._wait_for_access(client, vm_id)
            except Exception as exc:
                logger.error(
                    "provider VM creation failed",
                    extra={"vm_name": command.name, "provider_id": command.provider_id},
                    exc_info=True,
                )
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
            **(
                {"provider_endpoint_url": provider_endpoint_url}
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
        logger.info(
            "Requestor VM is running and access saved",
            extra={
                "vm_name": command.name,
                "vm_id": access.get("vm_id") or record.vm_id,
            },
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
            logger.debug(
                "Polling provider VM access",
                extra={"vm_id": vm_id, "status": last_status},
            )
            if last_status == "running":
                return await client.get_vm_access(vm_id)
            await asyncio.sleep(2.0)
        logger.warning(
            "Timed out waiting for provider VM access",
            extra={"vm_id": vm_id, "last_status": last_status},
        )
        raise ExternalServiceError(
            f"VM did not become ready in time (status={last_status})"
        )

    async def list_vms(self) -> list[VMRecord]:
        logger.debug("Listing requestor VMs")
        return self.vm_repo.list()

    async def get_vm(self, name: str) -> VMRecord:
        vm = self.vm_repo.require(name)
        return await self._ensure_ssh_user(vm)

    async def _ensure_ssh_user(self, vm: VMRecord) -> VMRecord:
        if vm.config.get("ssh_user"):
            return vm

        async with self._client_for_vm(vm) as client:
            access = await client.get_vm_access(vm.vm_id)
        logger.debug("Backfilled VM SSH access details", extra={"vm_name": vm.name})

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
        async with self._client_for_vm(vm) as client:
            await client.start_vm(vm.vm_id)
        self.vm_repo.update_status(name, "running")
        logger.info("Requestor VM started", extra={"vm_name": name, "vm_id": vm.vm_id})
        return self.vm_repo.require(name)

    async def stop_vm(self, name: str) -> VMRecord:
        vm = self.vm_repo.require(name)
        async with self._client_for_vm(vm) as client:
            await client.stop_vm(vm.vm_id)
        self.vm_repo.update_status(name, "stopped")
        logger.info("Requestor VM stopped", extra={"vm_name": name, "vm_id": vm.vm_id})
        return self.vm_repo.require(name)

    async def restart_vm(self, name: str) -> VMRecord:
        vm = self.vm_repo.require(name)
        async with self._client_for_vm(vm) as client:
            result = await client.restart_vm(vm.vm_id)
        self._sync_record(name, result)
        logger.info(
            "Requestor VM restarted", extra={"vm_name": name, "vm_id": vm.vm_id}
        )
        return self.vm_repo.require(name)

    async def suspend_vm(self, name: str) -> VMRecord:
        vm = self.vm_repo.require(name)
        async with self._client_for_vm(vm) as client:
            result = await client.suspend_vm(vm.vm_id)
        self._sync_record(name, result, fallback_status="suspended")
        logger.info(
            "Requestor VM suspended", extra={"vm_name": name, "vm_id": vm.vm_id}
        )
        return self.vm_repo.require(name)

    async def resume_vm(self, name: str) -> VMRecord:
        vm = self.vm_repo.require(name)
        async with self._client_for_vm(vm) as client:
            result = await client.resume_vm(vm.vm_id)
        self._sync_record(name, result, fallback_status="running")
        logger.info("Requestor VM resumed", extra={"vm_name": name, "vm_id": vm.vm_id})
        return self.vm_repo.require(name)

    async def resize_vm(self, name: str, command: ResizeVMCommand) -> VMRecord:
        vm = self.vm_repo.require(name)
        if vm.config.get("stream_id") is not None and command.stream_id is None:
            logger.warning(
                "Paid VM resize missing replacement stream", extra={"vm_name": name}
            )
            raise ValidationError("resizing a paid VM requires a replacement stream")
        async with self._client_for_vm(vm) as client:
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
        logger.info("Requestor VM resized", extra={"vm_name": name, "vm_id": vm.vm_id})
        return self.vm_repo.require(name)

    async def list_provider_images(self, provider_id: str) -> list[dict]:
        provider = await self.discovery_service.require_provider(
            provider_id, ProviderSearchQuery()
        )
        endpoint_url = self._require_provider_endpoint(provider, provider_id)
        async with self.provider_client_factory.for_provider_endpoint(
            endpoint_url
        ) as client:
            return await client.list_images()

    async def list_snapshots(self, name: str) -> list[dict]:
        vm = self.vm_repo.require(name)
        async with self._client_for_vm(vm) as client:
            return await client.list_snapshots(vm.vm_id)

    async def create_snapshot(self, name: str, command: SnapshotCommand) -> dict:
        vm = self.vm_repo.require(name)
        async with self._client_for_vm(vm) as client:
            snapshot = await client.create_snapshot(
                vm.vm_id, command.name, command.comment
            )
        logger.info("Requestor VM snapshot created", extra={"vm_name": name})
        return snapshot

    async def restore_snapshot(self, name: str, snapshot_name: str) -> VMRecord:
        vm = self.vm_repo.require(name)
        async with self._client_for_vm(vm) as client:
            result = await client.restore_snapshot(vm.vm_id, snapshot_name)
        self._sync_record(name, result)
        logger.info(
            "Requestor VM snapshot restored",
            extra={"vm_name": name, "snapshot_name": snapshot_name},
        )
        return self.vm_repo.require(name)

    async def delete_snapshot(self, name: str, snapshot_name: str) -> None:
        vm = self.vm_repo.require(name)
        async with self._client_for_vm(vm) as client:
            await client.delete_snapshot(vm.vm_id, snapshot_name)
        logger.info(
            "Requestor VM snapshot deleted",
            extra={"vm_name": name, "snapshot_name": snapshot_name},
        )

    async def clone_vm(self, source_name: str, command: CloneVMCommand) -> VMRecord:
        source = self.vm_repo.require(source_name)
        if self.vm_repo.get(command.name) is not None:
            raise ConflictError(f"VM with name '{command.name}' already exists")
        if source.config.get("stream_id") is not None and command.stream_id is None:
            logger.warning(
                "Paid VM clone missing replacement stream",
                extra={
                    "source_vm_name": source_name,
                    "destination_vm_name": command.name,
                },
            )
            raise ValidationError("cloning a paid VM requires a replacement stream")
        async with self._client_for_vm(source) as client:
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
        logger.info(
            "Requestor VM cloned",
            extra={"source_vm_name": source_name, "destination_vm_name": command.name},
        )
        return self.vm_repo.require(command.name)

    async def delete_vm(self, name: str) -> None:
        vm = self.vm_repo.require(name)
        await self._terminate_stream_for_delete(vm)
        async with self._client_for_vm(vm) as client:
            await client.destroy_vm(vm.vm_id)
        self.vm_repo.delete(name)
        logger.info("Requestor VM deleted", extra={"vm_name": name, "vm_id": vm.vm_id})

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
                logger.warning(
                    "Ignoring missing stream during VM delete",
                    extra={"vm_name": vm.name, "stream_id": stream_id},
                )
                return
            logger.error(
                "Failed to terminate stream during VM delete",
                extra={"vm_name": vm.name, "stream_id": stream_id},
                exc_info=True,
            )
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

    def _client_for_vm(self, vm: VMRecord):
        endpoint_url = vm.config.get("provider_endpoint_url")
        logger.debug(
            "Creating provider client for VM",
            extra={"vm_name": vm.name, "provider_ip": vm.provider_ip},
        )
        if not endpoint_url:
            raise ValidationError("Provider endpoint URL not found for VM")
        return self.provider_client_factory.for_provider_endpoint(str(endpoint_url))

    def _require_provider_endpoint(self, provider: dict, provider_id: str) -> str:
        endpoint_url = provider.get("endpoint_url")
        try:
            return self.settings.get_provider_url(str(endpoint_url or ""))
        except ValueError as exc:
            logger.warning(
                "Provider advertisement missing endpoint",
                extra={"provider_id": provider_id},
            )
            raise ValidationError(
                "Provider endpoint URL not found in advertisement"
            ) from exc
