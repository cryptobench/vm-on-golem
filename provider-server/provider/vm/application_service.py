import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any

from provider.errors import ConflictError, ExternalServiceError, NotFoundError
from provider.payments.domain import LeasePayment
from provider.payments.errors import InvalidStreamError
from provider.payments.stream_status_service import ZERO_ADDRESS, StreamStatusService
from provider.webhooks.domain import WebhookEventType

from .domain import CreateVMCommand, CreateVMJobResult, LeaseTerminationResult
from .lifecycle import VMLifecycleState, creation_lifecycle, lifecycle_for_status
from .models import (
    MULTIPASS_SSH_USER,
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
        event_broadcaster: Any = None,
        webhook_service: Any = None,
        stream_client: Any = None,
    ):
        self.vm_service = vm_service
        self.settings = settings
        self.stream_status_service = stream_status_service
        self.job_store = job_store
        self.event_broadcaster = event_broadcaster
        self.webhook_service = webhook_service
        self.stream_client = stream_client

    def _setting(self, name: str, default: Any = None) -> Any:
        if isinstance(self.settings, dict):
            return self.settings.get(name, default)
        return getattr(self.settings, name, default)

    async def create_vm(self, command: CreateVMCommand) -> VMInfo | CreateVMJobResult:
        logger.info(
            "Provider VM create requested",
            extra={"vm_id": command.name, "async_mode": command.async_mode},
        )
        if not await self.stream_status_service.is_payment_required():
            raise InvalidStreamError("streaming payments required to create a VM")
        await self.stream_status_service.require_valid_lease(
            command.payment,
            requestor_address=command.action_signer,
            current_vm_id=command.name,
            vm_name=command.name,
            image=command.image or str(self._setting("DEFAULT_VM_IMAGE", "24.04")),
            resources=command.resources,
        )
        existing = await self._existing_create_result(command)
        if existing is not None:
            return existing

        config = VMConfig(
            name=command.name,
            image=command.image or str(self._setting("DEFAULT_VM_IMAGE", "24.04")),
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
            await self._emit_webhook(
                "vm.failed",
                command.name,
                "critical",
                "VM creation failed",
                {"error": str(exc)},
            )
            raise ExternalServiceError(
                f"failed to create VM {command.name}: {exc}"
            ) from exc
        try:
            stream_id = command.payment.stream_id if command.payment else None
            await self.stream_status_service.set_vm_stream(
                vm_info.id, stream_id, command.action_signer
            )
            logger.info(
                "Persisted VM stream mapping",
                extra={"vm_id": vm_info.id, "stream_id": stream_id},
            )
        except Exception as exc:
            logger.error(
                "failed to persist stream mapping after VM creation",
                extra={
                    "vm_id": vm_info.id,
                    "stream_id": command.payment.stream_id if command.payment else None,
                },
            )
            raise ExternalServiceError(
                f"failed to persist stream mapping for {vm_info.id}: {exc}"
            ) from exc
        logger.info(
            "Provider VM create completed",
            extra={"vm_id": vm_info.id, "status": str(vm_info.status)},
        )
        await self._publish_live(
            ["vms", "summary", "streams"],
            vm_id=vm_info.id,
            vm_scopes=["lifecycle", "access", "stream"],
        )
        await self._emit_webhook(
            "vm.ready",
            vm_info.id,
            "info",
            "VM is online",
            {"status": str(vm_info.status)},
        )
        return vm_info

    async def _existing_create_result(
        self, command: CreateVMCommand
    ) -> VMInfo | CreateVMJobResult | None:
        if command.payment is None:
            return None
        payment_stream_id = command.payment.stream_id if command.payment else None
        stream_map = self.stream_status_service.stream_map
        mapped_stream_id = await stream_map.get(command.name)
        job = await self._latest_create_job_for_vm(command.name)
        if mapped_stream_id is not None:
            if int(mapped_stream_id) != int(payment_stream_id):
                if job is not None and self._is_active_create_job(job):
                    raise ConflictError(
                        "VM creation job already exists for this VM name"
                    )
                try:
                    await self.vm_service.get_vm_status(command.name)
                except VMNotFoundError:
                    await self._remove_stale_stream_mapping(
                        command.name,
                        mapped_stream_id,
                        "mapped stream has no VM or active creation job",
                    )
                    return None
                raise ConflictError("VM name is already backed by another stream")
            owner = await self._mapped_owner(command.name)
            if owner and owner.lower() != str(command.action_signer or "").lower():
                raise ConflictError("VM name is already owned by another requestor")
            try:
                return await self.get_vm_status(command.name)
            except VMNotFoundError:
                if job and self._job_matches_create(job, command):
                    return self._job_result(job)
                await self._remove_stale_stream_mapping(
                    command.name,
                    mapped_stream_id,
                    "mapped stream has no VM or matching creation job",
                )
                return None

        if (
            job is not None
            and self._job_has_create_owner(job)
            and self._is_active_create_job(job)
        ):
            if not self._job_matches_create(job, command):
                raise ConflictError("VM creation job already exists for this VM name")
            return self._job_result(job)

        if hasattr(self.vm_service, "name_mapper"):
            multipass_name = await self.vm_service.name_mapper.get_multipass_name(
                command.name
            )
            if multipass_name:
                raise ConflictError("VM name already exists without a stream mapping")
        return None

    async def _mapped_owner(self, vm_id: str) -> str | None:
        get_owner = getattr(self.stream_status_service.stream_map, "get_owner", None)
        if get_owner is None:
            return None
        owner = await get_owner(vm_id)
        return str(owner) if owner else None

    async def _remove_stale_stream_mapping(
        self, vm_id: str, stream_id: int | str, reason: str
    ) -> None:
        logger.warning(
            "Removing stale VM stream mapping",
            extra={"vm_id": vm_id, "stream_id": int(stream_id), "reason": reason},
        )
        await self.stream_status_service.remove_vm_stream(vm_id)
        await self._publish_live(
            ["vms", "summary", "streams"],
            vm_id=vm_id,
            vm_scopes=["lifecycle", "access", "stream"],
        )

    async def _latest_create_job_for_vm(self, vm_id: str) -> dict[str, Any] | None:
        for job in await self.job_store.active_recent_jobs():
            if str(job.get("vm_id") or "") == vm_id:
                return job
        return None

    @staticmethod
    def _job_has_create_owner(job: dict[str, Any]) -> bool:
        return bool(job.get("requestor_address")) or job.get("stream_id") is not None

    @staticmethod
    def _is_active_create_job(job: dict[str, Any]) -> bool:
        if bool(job.get("transitioning")):
            return True
        return str(job.get("status") or "") in {"queued", "creating", "starting"}

    @staticmethod
    def _job_matches_create(job: dict[str, Any], command: CreateVMCommand) -> bool:
        owner = str(job.get("requestor_address") or "")
        if owner and owner.lower() != str(command.action_signer or "").lower():
            return False
        job_stream_id = job.get("stream_id")
        payment_stream_id = command.payment.stream_id if command.payment else None
        if job_stream_id is None or payment_stream_id is None:
            return job_stream_id == payment_stream_id
        return int(job_stream_id) == int(payment_stream_id)

    @staticmethod
    def _job_result(job: dict[str, Any]) -> CreateVMJobResult:
        return CreateVMJobResult(
            job_id=str(job["job_id"]),
            vm_id=str(job["vm_id"]),
            status=str(job["status"]),
            lifecycle_stage=str(job["lifecycle_stage"]),
            status_message=str(job["status_message"]),
            progress=int(job["progress"]),
            transitioning=bool(job["transitioning"]),
            next_poll_seconds=int(job["next_poll_seconds"]),
        )

    async def _schedule_create_vm(
        self, command: CreateVMCommand, config: VMConfig
    ) -> CreateVMJobResult:
        job_id = str(uuid.uuid4())
        initial = creation_lifecycle(
            "queued",
            "Queued VM creation",
            0,
        )
        await self.job_store.create_job(
            job_id,
            command.name,
            status=initial.status.value,
            lifecycle_stage=initial.lifecycle_stage,
            status_message=initial.status_message,
            progress=initial.progress,
            transitioning=initial.transitioning,
            next_poll_seconds=initial.next_poll_seconds,
            requestor_address=command.action_signer,
            stream_id=command.payment.stream_id if command.payment else None,
        )
        await self._publish_live(
            ["vms", "summary"],
            vm_id=command.name,
            vm_scopes=["lifecycle", "job", "access"],
        )
        logger.info(
            "Scheduled VM creation job",
            extra={"job_id": job_id, "vm_id": command.name},
        )

        async def _update_progress(progress: VMLifecycleState) -> None:
            await self.job_store.update_job(
                job_id,
                status=progress.status.value,
                lifecycle_stage=progress.lifecycle_stage,
                status_message=progress.status_message,
                progress=progress.progress,
                transitioning=progress.transitioning,
                next_poll_seconds=progress.next_poll_seconds,
            )
            await self._publish_live(
                ["vms", "summary"],
                vm_id=command.name,
                vm_scopes=["lifecycle", "job", "access"],
            )

        async def _run_creation() -> None:
            try:
                await self.stream_status_service.require_valid_lease(
                    command.payment,
                    requestor_address=command.action_signer,
                    current_vm_id=command.name,
                )
                vm_info = await self.vm_service.create_vm_with_progress(
                    config,
                    _update_progress,
                )
                stream_id = command.payment.stream_id if command.payment else None
                await self.stream_status_service.set_vm_stream(
                    vm_info.id, stream_id, command.action_signer
                )
                await self._publish_live(
                    ["vms", "summary", "streams"],
                    vm_id=vm_info.id,
                    vm_scopes=["lifecycle", "access", "job", "stream"],
                )
                ready = lifecycle_for_status(
                    VMStatus.RUNNING,
                    stage="ready",
                    message="VM is online",
                    progress=100,
                )
                await self.job_store.update_job(
                    job_id,
                    status=ready.status.value,
                    lifecycle_stage=ready.lifecycle_stage,
                    status_message=ready.status_message,
                    progress=ready.progress,
                    transitioning=False,
                    next_poll_seconds=ready.next_poll_seconds,
                )
                await self._publish_live(
                    ["vms", "summary", "streams"],
                    vm_id=vm_info.id,
                    vm_scopes=["lifecycle", "access", "job", "stream"],
                )
                logger.info(
                    "Create VM job completed",
                    extra={"job_id": job_id, "vm_id": vm_info.id},
                )
                await self._emit_webhook(
                    "vm.ready",
                    vm_info.id,
                    "info",
                    "VM is online",
                    {"job_id": job_id, "status": str(vm_info.status)},
                )
            except Exception as exc:
                logger.error(
                    "Create VM job failed",
                    extra={"job_id": job_id, "vm_id": command.name},
                    exc_info=True,
                )
                await self.job_store.update_job(
                    job_id,
                    status="failed",
                    lifecycle_stage="failed",
                    status_message="VM creation failed",
                    progress=100,
                    transitioning=False,
                    next_poll_seconds=8,
                    error=str(exc),
                )
                await self._publish_live(
                    ["vms", "summary"],
                    vm_id=command.name,
                    vm_scopes=["lifecycle", "access", "job"],
                )
                await self._emit_webhook(
                    "vm.failed",
                    command.name,
                    "critical",
                    "VM creation failed",
                    {"job_id": job_id, "error": str(exc)},
                )

        asyncio.create_task(_run_creation(), name=f"create-vm:{command.name}")
        return CreateVMJobResult(
            job_id=job_id,
            vm_id=command.name,
            status=initial.status.value,
            lifecycle_stage=initial.lifecycle_stage,
            status_message=initial.status_message,
            progress=initial.progress,
            transitioning=initial.transitioning,
            next_poll_seconds=initial.next_poll_seconds,
        )

    async def get_create_job(self, job_id: str) -> dict[str, Any]:
        logger.debug("Fetching VM creation job", extra={"job_id": job_id})
        job = await self.job_store.get_job(job_id)
        if not job:
            raise NotFoundError("job not found")
        return job

    async def list_vms(self) -> list[VMInfo]:
        try:
            logger.debug("Listing provider VMs")
            real_vms = await self.vm_service.list_vms()
            by_id = {vm.id: vm for vm in real_vms}
            records = await self._stream_records()
            for vm_id, record in records.items():
                if record.get("state") == "terminated":
                    by_id[vm_id] = self._terminal_vm_info(vm_id, record)
            for job in await self.job_store.active_recent_jobs():
                vm_id = str(job.get("vm_id") or "")
                if not vm_id:
                    continue
                if vm_id not in by_id or (
                    self._is_active_create_job(job)
                    and by_id[vm_id].status == VMStatus.UNKNOWN
                ):
                    by_id[vm_id] = self._vm_from_create_job(job)
            return list(by_id.values())
        except Exception as exc:
            raise ExternalServiceError(f"failed to list VMs: {exc}") from exc

    def _vm_from_create_job(self, job: dict[str, Any]) -> VMInfo:
        vm_id = str(job["vm_id"])
        status = str(job.get("status") or "").lower()
        failed = status == "failed"
        resources = None
        if hasattr(self.vm_service, "resource_tracker"):
            resources = self.vm_service.resource_tracker.get_allocated_resources_for(
                vm_id
            )
        return VMInfo(
            id=vm_id,
            name=vm_id,
            status=VMStatus.ERROR if failed else VMStatus.CREATING,
            resources=resources or VMResources(cpu=1, memory=1, storage=10),
            ip_address=None,
            ssh_port=None,
            lifecycle_stage=str(
                job.get("lifecycle_stage") or ("failed" if failed else "queued")
            ),
            status_message=str(
                job.get("error")
                or job.get("status_message")
                or ("VM creation failed" if failed else "Queued VM creation")
            ),
            progress=int(job.get("progress") or (100 if failed else 0)),
            transitioning=bool(job.get("transitioning")) and not failed,
            next_poll_seconds=int(job.get("next_poll_seconds") or 2),
            created_at=_job_datetime(job.get("created_at")),
            updated_at=_job_datetime(job.get("updated_at")),
            error_message=str(job.get("error")) if job.get("error") else None,
        )

    async def get_vm_status(self, vm_id: str) -> VMInfo:
        terminal = await self.stream_status_service.terminal_record(vm_id)
        if terminal is not None:
            return self._terminal_vm_info(vm_id, terminal)
        try:
            logger.debug("Fetching provider VM status", extra={"vm_id": vm_id})
            vm = await self.vm_service.get_vm_status(vm_id)
            job = await self._latest_create_job_for_vm(vm_id)
            if (
                job is not None
                and self._is_active_create_job(job)
                and vm.status == VMStatus.UNKNOWN
            ):
                return self._vm_from_create_job(job)
            return vm
        except VMNotFoundError as exc:
            return await self._synthetic_creating_status(vm_id, exc)
        except Exception as exc:
            raise ExternalServiceError(
                f"failed to get VM status for {vm_id}: {exc}"
            ) from exc

    async def _synthetic_creating_status(
        self, vm_id: str, original_error: VMNotFoundError
    ) -> VMInfo:
        job = await self._latest_create_job_for_vm(vm_id)
        if job is not None:
            return self._vm_from_create_job(job)

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

        logger.debug("Returning synthetic creating VM status", extra={"vm_id": vm_id})
        return VMInfo(
            id=vm_id,
            name=vm_id,
            status=VMStatus.CREATING,
            resources=resources,
            ip_address=None,
            ssh_port=None,
            lifecycle_stage="provisioning",
            status_message="VM is being provisioned",
            progress=50,
            transitioning=True,
            next_poll_seconds=2,
        )

    async def get_vm_access(self, vm_id: str) -> VMAccessInfo | dict[str, Any]:
        try:
            logger.debug("Fetching provider VM access", extra={"vm_id": vm_id})
            vm = await self.get_vm_status(vm_id)
        except VMNotFoundError:
            raise
        except Exception as exc:
            raise ExternalServiceError(
                f"failed to get VM access for {vm_id}: {exc}"
            ) from exc
        if vm is None:
            raise VMNotFoundError(f"VM {vm_id} not found")

        if vm.status == VMStatus.TERMINATED:
            return {
                "vm_id": vm_id,
                "multipass_name": None,
                "status": VMStatus.TERMINATED.value,
                "lifecycle_stage": vm.lifecycle_stage,
                "status_message": vm.status_message,
                "progress": 100,
                "transitioning": False,
                "next_poll_seconds": 8,
                "ssh_port": None,
                "ssh_user": MULTIPASS_SSH_USER,
            }

        multipass_name = None
        if hasattr(self.vm_service, "name_mapper"):
            multipass_name = await self.vm_service.name_mapper.get_multipass_name(vm_id)

        if vm.ssh_port is not None and not multipass_name:
            raise VMNotFoundError(f"VM {vm_id} not found")

        if vm.ssh_port is None or not multipass_name:
            lifecycle = lifecycle_for_status(
                vm.status,
                stage=vm.lifecycle_stage or "configuring_access",
                message=vm.status_message or "Waiting for SSH access",
                progress=vm.progress or 90,
            )
            return {
                "vm_id": vm_id,
                "multipass_name": multipass_name,
                "status": lifecycle.status.value,
                "lifecycle_stage": lifecycle.lifecycle_stage,
                "status_message": lifecycle.status_message,
                "progress": lifecycle.progress,
                "transitioning": lifecycle.transitioning,
                "next_poll_seconds": lifecycle.next_poll_seconds,
                "ssh_port": None,
                "ssh_user": MULTIPASS_SSH_USER,
            }

        return VMAccessInfo(
            ssh_host=str(self._setting("PUBLIC_IP", None) or "localhost"),
            ssh_port=int(vm.ssh_port),
            ssh_user=MULTIPASS_SSH_USER,
            vm_id=vm_id,
            multipass_name=multipass_name,
        )

    async def stop_vm(self, vm_id: str, action_signer: str | None = None) -> VMInfo:
        try:
            await self.stream_status_service.require_vm_action_authorized(
                vm_id, action_signer
            )
            vm = await self.vm_service.stop_vm(vm_id)
            logger.info("Provider VM stopped", extra={"vm_id": vm_id})
            await self._publish_live(
                ["vms", "summary", "monitoring", "metrics"],
                vm_id=vm_id,
                vm_scopes=["lifecycle", "access", "metrics_live"],
            )
            await self._emit_webhook(
                "vm.stopped",
                vm_id,
                "info",
                "VM stopped",
                {"status": str(vm.status)},
            )
            return vm
        except VMNotFoundError:
            raise
        except Exception as exc:
            logger.error(
                "Provider VM stop failed", extra={"vm_id": vm_id}, exc_info=True
            )
            raise ExternalServiceError(f"failed to stop VM {vm_id}: {exc}") from exc

    async def _require_active_vm_payment(
        self, vm_id: str, action_signer: str | None
    ) -> None:
        if not await self.stream_status_service.is_payment_required():
            return
        stream_id = await self.stream_status_service.stream_map.get(vm_id)
        if stream_id is None:
            raise InvalidStreamError("no payment stream mapped for VM")
        status = await self.stream_status_service.get_vm_stream_status(vm_id)
        await self.stream_status_service.require_valid_lease(
            LeasePayment(
                stream_id=int(stream_id),
                lease_id=status.chain.leaseId,
                terms_hash=status.chain.termsHash,
                rate_per_second_wei=status.chain.ratePerSecond,
            ),
            requestor_address=action_signer,
            current_vm_id=vm_id,
        )

    async def start_vm(self, vm_id: str, action_signer: str | None = None) -> VMInfo:
        try:
            await self._require_active_vm_payment(vm_id, action_signer)
            vm = await self.vm_service.start_vm(vm_id)
            logger.info("Provider VM started", extra={"vm_id": vm_id})
            await self._publish_live(
                ["vms", "summary", "monitoring", "metrics"],
                vm_id=vm_id,
                vm_scopes=["lifecycle", "access", "metrics_live"],
            )
            return vm
        except VMNotFoundError:
            raise
        except Exception as exc:
            logger.error(
                "Provider VM start failed", extra={"vm_id": vm_id}, exc_info=True
            )
            raise ExternalServiceError(f"failed to start VM {vm_id}: {exc}") from exc

    async def restart_vm(self, vm_id: str, action_signer: str | None = None) -> VMInfo:
        try:
            await self._require_active_vm_payment(vm_id, action_signer)
            vm = await self.vm_service.restart_vm(vm_id)
            logger.info("Provider VM restarted", extra={"vm_id": vm_id})
            await self._publish_live(
                ["vms", "summary", "monitoring", "metrics"],
                vm_id=vm_id,
                vm_scopes=["lifecycle", "access", "metrics_live"],
            )
            return vm
        except VMNotFoundError:
            raise
        except Exception as exc:
            logger.error(
                "Provider VM restart failed", extra={"vm_id": vm_id}, exc_info=True
            )
            raise ExternalServiceError(f"failed to restart VM {vm_id}: {exc}") from exc

    async def suspend_vm(self, vm_id: str, action_signer: str | None = None) -> VMInfo:
        try:
            await self.stream_status_service.require_vm_action_authorized(
                vm_id, action_signer
            )
            vm = await self.vm_service.suspend_vm(vm_id)
            logger.info("Provider VM suspended", extra={"vm_id": vm_id})
            await self._publish_live(
                ["vms", "summary", "monitoring", "metrics"],
                vm_id=vm_id,
                vm_scopes=["lifecycle", "access", "metrics_live"],
            )
            return vm
        except VMNotFoundError:
            raise
        except Exception as exc:
            logger.error(
                "Provider VM suspend failed", extra={"vm_id": vm_id}, exc_info=True
            )
            raise ExternalServiceError(f"failed to suspend VM {vm_id}: {exc}") from exc

    async def resize_vm(
        self,
        vm_id: str,
        resources: VMResources,
        action_signer: str | None = None,
        payment: LeasePayment | None = None,
    ) -> VMInfo:
        try:
            if payment is not None:
                await self.stream_status_service.require_valid_lease(
                    payment,
                    requestor_address=action_signer,
                    current_vm_id=vm_id,
                    vm_name=vm_id,
                    image=str(self._setting("DEFAULT_VM_IMAGE", "24.04")),
                    resources=resources,
                )
            else:
                await self.stream_status_service.require_vm_action_authorized(
                    vm_id, action_signer
                )
            vm = await self.vm_service.resize_vm(vm_id, resources)
            if payment is not None:
                await self.stream_status_service.set_vm_stream(
                    vm_id, payment.stream_id, action_signer
                )
            logger.info("Provider VM resized", extra={"vm_id": vm_id})
            await self._publish_live(
                ["vms", "summary", "monitoring", "metrics", "streams"],
                vm_id=vm_id,
                vm_scopes=["lifecycle", "access", "metrics_live", "stream"],
            )
            return vm
        except VMNotFoundError:
            raise
        except Exception as exc:
            logger.error(
                "Provider VM resize failed", extra={"vm_id": vm_id}, exc_info=True
            )
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
        self,
        vm_id: str,
        name: str | None = None,
        comment: str | None = None,
        action_signer: str | None = None,
    ) -> VMSnapshot:
        try:
            await self.stream_status_service.require_vm_action_authorized(
                vm_id, action_signer
            )
            snapshot = await self.vm_service.create_snapshot(vm_id, name, comment)
            logger.info(
                "Provider VM snapshot created",
                extra={"vm_id": vm_id, "snapshot_name": snapshot.name},
            )
            await self._publish_live([], vm_id=vm_id, vm_scopes=["snapshots"])
            return snapshot
        except VMNotFoundError:
            raise
        except Exception as exc:
            raise ExternalServiceError(
                f"failed to create snapshot for VM {vm_id}: {exc}"
            ) from exc

    async def restore_snapshot(
        self,
        vm_id: str,
        snapshot_name: str,
        action_signer: str | None = None,
    ) -> VMInfo:
        try:
            await self.stream_status_service.require_vm_action_authorized(
                vm_id, action_signer
            )
            vm = await self.vm_service.restore_snapshot(vm_id, snapshot_name)
            logger.info(
                "Provider VM snapshot restored",
                extra={"vm_id": vm_id, "snapshot_name": snapshot_name},
            )
            await self._publish_live(
                ["vms", "summary", "monitoring", "metrics"],
                vm_id=vm_id,
                vm_scopes=["lifecycle", "access", "snapshots", "metrics_live"],
            )
            return vm
        except VMNotFoundError:
            raise
        except Exception as exc:
            raise ExternalServiceError(
                f"failed to restore snapshot {snapshot_name} for VM {vm_id}: {exc}"
            ) from exc

    async def delete_snapshot(
        self,
        vm_id: str,
        snapshot_name: str,
        action_signer: str | None = None,
    ) -> None:
        try:
            await self.stream_status_service.require_vm_action_authorized(
                vm_id, action_signer
            )
            await self.vm_service.delete_snapshot(vm_id, snapshot_name)
            logger.info(
                "Provider VM snapshot deleted",
                extra={"vm_id": vm_id, "snapshot_name": snapshot_name},
            )
            await self._publish_live([], vm_id=vm_id, vm_scopes=["snapshots"])
        except VMNotFoundError:
            raise
        except Exception as exc:
            raise ExternalServiceError(
                f"failed to delete snapshot {snapshot_name} for VM {vm_id}: {exc}"
            ) from exc

    async def clone_vm(
        self,
        source_vm_id: str,
        destination_vm_id: str,
        action_signer: str | None = None,
    ) -> VMInfo:
        try:
            await self.stream_status_service.require_vm_action_authorized(
                source_vm_id, action_signer
            )
            vm = await self.vm_service.clone_vm(source_vm_id, destination_vm_id)
            logger.info(
                "Provider VM cloned",
                extra={
                    "source_vm_id": source_vm_id,
                    "destination_vm_id": destination_vm_id,
                },
            )
            await self._publish_live(
                ["vms", "summary", "monitoring", "metrics"],
                vm_id=destination_vm_id,
                vm_scopes=["lifecycle", "access", "metrics_live"],
            )
            return vm
        except VMNotFoundError:
            raise
        except Exception as exc:
            raise ExternalServiceError(
                f"failed to clone VM {source_vm_id}: {exc}"
            ) from exc

    async def delete_vm(self, vm_id: str, action_signer: str | None = None) -> None:
        if await self.stream_status_service.is_payment_required():
            await self.stream_status_service.require_vm_action_authorized(
                vm_id, action_signer
            )
            await self.stream_status_service.verify_vm_stream_terminated(vm_id)
            record = await self.stream_status_service.terminal_record(vm_id)
            if record is None:
                await self.stream_status_service.mark_vm_stream_terminated(
                    vm_id,
                    terminated_by="requestor",
                    termination_reason="requestor_terminated",
                    settlement_tx_hash=None,
                    cleanup_state="not_started",
                )
            await self._delete_terminated_vm(vm_id)
            await self._emit_webhook(
                "vm.deleted",
                vm_id,
                "info",
                "VM lease was terminated by requestor",
                {},
            )
            return

        try:
            await self.stream_status_service.require_vm_action_authorized(
                vm_id, action_signer
            )
            await self.vm_service.delete_vm(vm_id)
            await self.stream_status_service.remove_vm_stream(vm_id)
            logger.info("Provider VM deleted", extra={"vm_id": vm_id})
            await self._publish_live(
                ["vms", "summary", "streams", "monitoring", "metrics"],
                vm_id=vm_id,
                vm_scopes=["lifecycle", "access", "stream", "metrics_live"],
            )
            await self._emit_webhook(
                "vm.deleted",
                vm_id,
                "info",
                "VM deleted",
                {},
            )
        except VMNotFoundError:
            await self.stream_status_service.remove_vm_stream(vm_id)
            logger.warning(
                "Provider VM delete target not found", extra={"vm_id": vm_id}
            )
            await self._publish_live(
                ["vms", "summary", "streams", "monitoring", "metrics"],
                vm_id=vm_id,
                vm_scopes=["lifecycle", "access", "stream", "metrics_live"],
            )
            raise
        except Exception as exc:
            logger.error(
                "Provider VM delete failed", extra={"vm_id": vm_id}, exc_info=True
            )
            raise ExternalServiceError(f"failed to delete VM {vm_id}: {exc}") from exc

    async def terminate_lease_by_provider(self, vm_id: str) -> LeaseTerminationResult:
        record = await self._required_stream_record(vm_id)
        if record["state"] == "terminated":
            if record.get("cleanup_state") != "completed":
                await self._delete_terminated_vm(vm_id)
                record = await self._required_stream_record(vm_id)
            return self._lease_termination_result(vm_id, record)

        stream_id = int(record["stream_id"])
        settlement_tx_hash: str | None = None
        try:
            stream_client = self._stream_client()
            if stream_client is None:
                raise RuntimeError("provider stream payment client unavailable")
            settlement_tx_hash = stream_client.terminate(stream_id)
        except Exception as exc:
            if not await self._is_chain_stream_terminated(stream_id):
                logger.error(
                    "Provider lease termination failed",
                    extra={"vm_id": vm_id, "stream_id": stream_id},
                    exc_info=True,
                )
                raise ExternalServiceError(
                    f"failed to terminate lease for {vm_id}: {exc}"
                ) from exc

        await self.stream_status_service.mark_vm_stream_terminated(
            vm_id,
            terminated_by="provider",
            termination_reason="provider_terminated",
            settlement_tx_hash=settlement_tx_hash,
            cleanup_state="not_started",
        )
        await self._delete_terminated_vm(vm_id)
        record = await self._required_stream_record(vm_id)
        logger.info(
            "Provider lease terminated",
            extra={"vm_id": vm_id, "stream_id": stream_id},
        )
        await self._emit_webhook(
            "vm.deleted",
            vm_id,
            "info",
            "VM lease was terminated by provider",
            {"stream_id": stream_id, "settlement_tx_hash": settlement_tx_hash},
        )
        return self._lease_termination_result(vm_id, record)

    async def cleanup_requestor_terminated_stream(
        self, vm_id: str, stream_id: int
    ) -> None:
        if not await self._is_chain_stream_terminated(int(stream_id)):
            return
        record = await self.stream_status_service.terminal_record(vm_id)
        if record is None:
            await self.stream_status_service.mark_vm_stream_terminated(
                vm_id,
                terminated_by="requestor",
                termination_reason="requestor_terminated",
                settlement_tx_hash=None,
                cleanup_state="not_started",
            )
        await self._delete_terminated_vm(vm_id)

    async def _delete_terminated_vm(self, vm_id: str) -> None:
        try:
            await self.vm_service.delete_vm(vm_id)
        except VMNotFoundError:
            logger.info(
                "Terminated lease VM already deleted",
                extra={"vm_id": vm_id},
            )
        except Exception as exc:
            await self.stream_status_service.set_vm_stream_cleanup_state(
                vm_id, "failed"
            )
            await self._publish_live(
                ["vms", "summary", "streams", "monitoring", "metrics"],
                vm_id=vm_id,
                vm_scopes=["lifecycle", "access", "stream", "metrics_live"],
            )
            logger.error(
                "Terminated lease VM cleanup failed",
                extra={"vm_id": vm_id},
                exc_info=True,
            )
            raise ExternalServiceError(
                f"lease terminated but failed to delete VM {vm_id}: {exc}"
            ) from exc

        await self.stream_status_service.set_vm_stream_cleanup_state(vm_id, "completed")
        await self._publish_live(
            ["vms", "summary", "streams", "monitoring", "metrics"],
            vm_id=vm_id,
            vm_scopes=["lifecycle", "access", "stream", "metrics_live"],
        )

    async def _is_chain_stream_terminated(self, stream_id: int) -> bool:
        reader = self.stream_status_service._reader()
        try:
            stream = reader.get_stream(int(stream_id))
        except Exception as exc:
            raise ExternalServiceError(f"stream lookup failed: {exc}") from exc
        return str(stream.get("recipient") or "").lower() == ZERO_ADDRESS

    async def _required_stream_record(self, vm_id: str) -> dict[str, Any]:
        record = await self.stream_status_service._stream_record(vm_id)
        if record is None:
            raise NotFoundError("no stream mapped for this VM")
        return record

    async def _stream_records(self) -> dict[str, dict[str, Any]]:
        records = getattr(self.stream_status_service.stream_map, "records", None)
        if records is None:
            raise RuntimeError("structured stream map is required")
        return await records()

    def _terminal_vm_info(self, vm_id: str, record: dict[str, Any]) -> VMInfo:
        terminated_by = str(record.get("terminated_by") or "requestor")
        message = (
            "VM lease was terminated by provider"
            if terminated_by == "provider"
            else "VM lease was terminated by requestor"
        )
        resources = None
        if hasattr(self.vm_service, "resource_tracker"):
            resources = self.vm_service.resource_tracker.get_allocated_resources_for(
                vm_id
            )
        return VMInfo(
            id=vm_id,
            name=vm_id,
            status=VMStatus.TERMINATED,
            resources=resources or VMResources(cpu=1, memory=1, storage=10),
            ip_address=None,
            ssh_port=None,
            lifecycle_stage=str(record.get("termination_reason") or "terminated"),
            status_message=message,
            progress=100,
            transitioning=False,
            next_poll_seconds=8,
        )

    def _lease_termination_result(
        self, vm_id: str, record: dict[str, Any]
    ) -> LeaseTerminationResult:
        return LeaseTerminationResult(
            vm=self._terminal_vm_info(vm_id, record),
            stream_id=int(record["stream_id"]),
            payment_state="terminated",
            termination_reason=str(record["termination_reason"]),
            terminated_by=str(record["terminated_by"]),
            terminated_at=record.get("terminated_at"),
            settlement_tx_hash=record.get("settlement_tx_hash"),
            cleanup_state=str(record["cleanup_state"]),
        )

    def _stream_client(self) -> Any:
        if self.stream_client is None:
            return None
        if hasattr(self.stream_client, "terminate"):
            return self.stream_client
        return self.stream_client()

    async def _publish_live(
        self,
        scopes: list[str],
        *,
        vm_id: str | None = None,
        vm_scopes: list[str] | None = None,
    ) -> None:
        if self.event_broadcaster is None:
            return
        await self.event_broadcaster.publish_provider(scopes)
        if vm_id:
            await self.event_broadcaster.publish_vm(vm_id, vm_scopes or scopes)

    async def _emit_webhook(
        self,
        event_type: WebhookEventType,
        vm_id: str,
        severity: str,
        summary: str,
        data: dict[str, Any],
    ) -> None:
        if self.webhook_service is None:
            return
        await self.webhook_service.emit(
            event_type,
            resource_type="vm",
            resource_id=vm_id,
            severity=severity,
            summary=summary,
            data=data,
        )


def _job_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        return datetime.fromisoformat(value)
    from provider.utils.time import utc_now

    return utc_now()
