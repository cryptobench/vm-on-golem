import asyncio
from types import SimpleNamespace

import pytest

from provider.errors import ConflictError, ExternalServiceError
from provider.payments.domain import LeasePayment
from provider.payments.errors import InvalidStreamError
from provider.summary.service import ProviderSummaryService
from provider.vm.application_service import VMApplicationService
from provider.vm.domain import CreateVMCommand
from provider.vm.models import VMInfo, VMNotFoundError, VMResources, VMStatus


class FakeVMService:
    def __init__(self):
        self.resource_tracker = FakeResourceTracker()

    async def list_vms(self):
        return []

    async def delete_vm(self, vm_id: str) -> None:
        raise VMNotFoundError(f"VM {vm_id} not found")


class FakeResourceTracker:
    total_resources = VMResources(cpu=4, memory=8, storage=100)

    def get_allocated_resources_for(self, vm_id):
        return VMResources(cpu=2, memory=4, storage=20)

    def get_available_resources(self):
        return VMResources(cpu=2, memory=4, storage=80)


class FakeStreamStatusService:
    def __init__(self):
        self.removed = []
        self.terminated = []
        self.cleanup = []
        self.stream_map = FakeStreamMap()

    async def require_vm_action_authorized(self, vm_id, action_signer):
        return None

    async def remove_vm_stream(self, vm_id: str) -> None:
        self.removed.append(vm_id)

    async def is_payment_required(self):
        return True

    async def require_valid_lease(self, *args, **kwargs):
        return None

    async def set_vm_stream(self, *args, **kwargs):
        return None

    async def verify_vm_stream_terminated(self, vm_id):
        return None

    async def terminal_record(self, vm_id):
        return None

    async def mark_vm_stream_terminated(self, vm_id, **kwargs):
        self.terminated.append((vm_id, kwargs))
        return {
            "vm_id": vm_id,
            "stream_id": 1,
            "requestor_address": "0x3333333333333333333333333333333333333333",
            "state": "terminated",
            **kwargs,
        }

    async def set_vm_stream_cleanup_state(self, vm_id, cleanup_state):
        self.cleanup.append((vm_id, cleanup_state))
        return {
            "vm_id": vm_id,
            "stream_id": 1,
            "requestor_address": "0x3333333333333333333333333333333333333333",
            "state": "terminated",
            "terminated_by": "requestor",
            "termination_reason": "requestor_terminated",
            "terminated_at": "2026-05-14T12:00:00+00:00",
            "settlement_tx_hash": None,
            "cleanup_state": cleanup_state,
        }


class FakeStreamMap:
    async def get(self, vm_id):
        return None

    async def get_owner(self, vm_id):
        return None

    async def records(self):
        return {}

    async def get_record(self, vm_id):
        return None


class FakeJobStore:
    async def active_recent_jobs(self):
        return [
            {
                "job_id": "job-a",
                "vm_id": "vm-a",
                "status": "creating",
                "lifecycle_stage": "provisioning",
                "status_message": "Preparing guest",
                "progress": 40,
                "transitioning": True,
                "next_poll_seconds": 2,
                "error": None,
                "created_at": "2026-05-14T12:00:00+00:00",
                "updated_at": "2026-05-14T12:00:01+00:00",
            },
            {
                "job_id": "job-b",
                "vm_id": "vm-b",
                "status": "failed",
                "lifecycle_stage": "failed",
                "status_message": "VM creation failed",
                "progress": 100,
                "transitioning": False,
                "next_poll_seconds": 8,
                "error": "boom",
                "created_at": "2026-05-14T12:00:00+00:00",
                "updated_at": "2026-05-14T12:00:01+00:00",
            },
        ]


@pytest.mark.asyncio
async def test_delete_vm_removes_stream_mapping_when_vm_already_gone():
    stream_status = FakeStreamStatusService()
    service = VMApplicationService(
        vm_service=FakeVMService(),
        settings={},
        stream_status_service=stream_status,
        job_store=None,
    )

    await service.delete_vm("vm-id")

    assert stream_status.terminated[0][0] == "vm-id"
    assert stream_status.cleanup == [("vm-id", "completed")]


@pytest.mark.asyncio
async def test_list_vms_includes_active_and_failed_creation_jobs():
    service = VMApplicationService(
        vm_service=FakeVMService(),
        settings={},
        stream_status_service=FakeStreamStatusService(),
        job_store=FakeJobStore(),
    )

    rows = await service.list_vms()

    assert [row.id for row in rows] == ["vm-a", "vm-b"]
    assert rows[0].status == "creating"
    assert rows[0].transitioning is True
    assert rows[0].resources == VMResources(cpu=2, memory=4, storage=20)
    assert rows[1].status == "error"
    assert rows[1].error_message == "boom"


@pytest.mark.asyncio
async def test_summary_uses_canonical_vm_list():
    vm_app = VMApplicationService(
        vm_service=FakeVMService(),
        settings={},
        stream_status_service=FakeStreamStatusService(),
        job_store=FakeJobStore(),
    )
    summary = ProviderSummaryService(
        settings={},
        resource_tracker=FakeResourceTracker(),
        vm_service=vm_app,
    )

    result = await summary.get_summary()

    assert [item["id"] for item in result.vms] == ["vm-a", "vm-b"]
    assert result.vms[0]["status"] == "creating"
    assert result.vms[1]["status"] == "error"


class LifecycleVMService(FakeVMService):
    def __init__(self, fail_create=False):
        super().__init__()
        self.fail_create = fail_create

    async def create_vm(self, config):
        if self.fail_create:
            raise RuntimeError("boom")
        return VMInfo(
            id=config.name,
            name=config.name,
            status=VMStatus.RUNNING,
            resources=config.resources,
        )

    async def create_vm_with_progress(self, config, progress_callback):
        return await self.create_vm(config)

    async def stop_vm(self, vm_id):
        return VMInfo(
            id=vm_id,
            name=vm_id,
            status=VMStatus.STOPPED,
            resources=VMResources(cpu=1, memory=1, storage=10),
        )

    async def resize_vm(self, vm_id, resources):
        return VMInfo(
            id=vm_id,
            name=vm_id,
            status=VMStatus.RUNNING,
            resources=resources,
        )

    async def delete_vm(self, vm_id: str) -> None:
        return None


class CapturingWebhookService:
    def __init__(self):
        self.events = []

    async def emit(self, event_type, **kwargs):
        self.events.append((event_type, kwargs))


@pytest.mark.asyncio
async def test_vm_lifecycle_emits_webhook_triggers():
    webhooks = CapturingWebhookService()
    service = VMApplicationService(
        vm_service=LifecycleVMService(),
        settings={},
        stream_status_service=FakeStreamStatusService(),
        job_store=FakeJobStore(),
        webhook_service=webhooks,
    )

    await service.create_vm(
        CreateVMCommand(
            name="vm-a",
            image="ubuntu",
            resources=VMResources(cpu=1, memory=1, storage=10),
            ssh_key="ssh-rsa test",
        )
    )
    await service.stop_vm("vm-a")
    await service.delete_vm("vm-a")

    failed_service = VMApplicationService(
        vm_service=LifecycleVMService(fail_create=True),
        settings={},
        stream_status_service=FakeStreamStatusService(),
        job_store=FakeJobStore(),
        webhook_service=webhooks,
    )
    with pytest.raises(Exception):
        await failed_service.create_vm(
            CreateVMCommand(
                name="vm-b",
                image="ubuntu",
                resources=VMResources(cpu=1, memory=1, storage=10),
                ssh_key="ssh-rsa test",
            )
        )

    assert [event[0] for event in webhooks.events] == [
        "vm.ready",
        "vm.stopped",
        "vm.deleted",
        "vm.failed",
    ]


class RecordingStreamStatusService(FakeStreamStatusService):
    def __init__(self):
        super().__init__()
        self.valid_lease_calls = []
        self.set_calls = []

    async def require_valid_lease(self, *args, **kwargs):
        self.valid_lease_calls.append((args, kwargs))

    async def set_vm_stream(self, *args, **kwargs):
        self.set_calls.append((args, kwargs))


class RecordingJobStore(FakeJobStore):
    def __init__(self):
        self.created = []
        self.updated = []

    async def active_recent_jobs(self):
        return []

    async def create_job(self, *args, **kwargs):
        self.created.append((args, kwargs))

    async def update_job(self, *args, **kwargs):
        self.updated.append((args, kwargs))


class FailedCreateJobStore(RecordingJobStore):
    async def active_recent_jobs(self):
        return [
            {
                "job_id": "job-failed",
                "vm_id": "vm-a",
                "status": "failed",
                "lifecycle_stage": "failed",
                "status_message": "VM creation failed",
                "progress": 100,
                "transitioning": False,
                "next_poll_seconds": 8,
                "error": "boom",
                "requestor_address": "0x3333333333333333333333333333333333333333",
                "stream_id": 123,
                "created_at": "2026-05-14T12:00:00+00:00",
                "updated_at": "2026-05-14T12:00:01+00:00",
            }
        ]


class ExistingStreamMap:
    def __init__(
        self, stream_id=123, owner="0x3333333333333333333333333333333333333333"
    ):
        self.stream_id = stream_id
        self.owner = owner

    async def get(self, vm_id):
        return self.stream_id

    async def get_owner(self, vm_id):
        return self.owner


class ExistingStreamStatusService(RecordingStreamStatusService):
    def __init__(self, stream_id=123):
        super().__init__()
        self.stream_map = ExistingStreamMap(stream_id=stream_id)


class ExistingVMService(LifecycleVMService):
    def __init__(self):
        super().__init__()
        self.create_calls = 0

    async def create_vm(self, config):
        self.create_calls += 1
        return await super().create_vm(config)

    async def get_vm_status(self, vm_id):
        return VMInfo(
            id=vm_id,
            name=vm_id,
            status=VMStatus.RUNNING,
            resources=VMResources(cpu=1, memory=1, storage=10),
        )


class MissingExistingVMService(ExistingVMService):
    async def get_vm_status(self, vm_id):
        raise VMNotFoundError(f"VM {vm_id} not found")


@pytest.mark.asyncio
async def test_async_create_rechecks_stream_without_recomputing_terms():
    stream_status = RecordingStreamStatusService()
    service = VMApplicationService(
        vm_service=LifecycleVMService(),
        settings={"DEFAULT_VM_IMAGE": "24.04"},
        stream_status_service=stream_status,
        job_store=RecordingJobStore(),
    )
    payment = LeasePayment(
        stream_id=123,
        lease_id="0x" + "11" * 32,
        terms_hash="0x" + "22" * 32,
        rate_per_second_wei=7,
        duration_seconds=3600,
    )

    await service.create_vm(
        CreateVMCommand(
            name="vm-a",
            image=None,
            resources=VMResources(cpu=1, memory=1, storage=10),
            ssh_key="ssh-rsa test",
            payment=payment,
            action_signer="0x3333333333333333333333333333333333333333",
            async_mode=True,
        )
    )
    for _ in range(20):
        if len(stream_status.valid_lease_calls) >= 2:
            break
        await asyncio.sleep(0)

    assert len(stream_status.valid_lease_calls) >= 2
    assert stream_status.valid_lease_calls[0][1]["resources"] == VMResources(
        cpu=1,
        memory=1,
        storage=10,
    )
    assert "resources" not in stream_status.valid_lease_calls[1][1]


@pytest.mark.asyncio
async def test_duplicate_create_returns_existing_vm_without_launching():
    vm_service = ExistingVMService()
    stream_status = ExistingStreamStatusService(stream_id=123)
    service = VMApplicationService(
        vm_service=vm_service,
        settings={"DEFAULT_VM_IMAGE": "24.04"},
        stream_status_service=stream_status,
        job_store=RecordingJobStore(),
    )
    payment = LeasePayment(
        stream_id=123,
        lease_id="0x" + "11" * 32,
        terms_hash="0x" + "22" * 32,
        rate_per_second_wei=7,
        duration_seconds=3600,
    )

    result = await service.create_vm(
        CreateVMCommand(
            name="vm-a",
            image=None,
            resources=VMResources(cpu=1, memory=1, storage=10),
            ssh_key="ssh-rsa test",
            payment=payment,
            action_signer="0x3333333333333333333333333333333333333333",
            async_mode=True,
        )
    )

    assert isinstance(result, VMInfo)
    assert result.id == "vm-a"
    assert vm_service.create_calls == 0


@pytest.mark.asyncio
async def test_duplicate_create_rejects_different_stream():
    service = VMApplicationService(
        vm_service=ExistingVMService(),
        settings={"DEFAULT_VM_IMAGE": "24.04"},
        stream_status_service=ExistingStreamStatusService(stream_id=123),
        job_store=RecordingJobStore(),
    )
    payment = LeasePayment(
        stream_id=456,
        lease_id="0x" + "11" * 32,
        terms_hash="0x" + "22" * 32,
        rate_per_second_wei=7,
        duration_seconds=3600,
    )

    with pytest.raises(ConflictError, match="another stream"):
        await service.create_vm(
            CreateVMCommand(
                name="vm-a",
                image=None,
                resources=VMResources(cpu=1, memory=1, storage=10),
                ssh_key="ssh-rsa test",
                payment=payment,
                action_signer="0x3333333333333333333333333333333333333333",
                async_mode=True,
            )
        )


@pytest.mark.asyncio
async def test_stale_stream_mapping_does_not_block_new_stream_create():
    vm_service = MissingExistingVMService()
    stream_status = ExistingStreamStatusService(stream_id=123)
    service = VMApplicationService(
        vm_service=vm_service,
        settings={"DEFAULT_VM_IMAGE": "24.04"},
        stream_status_service=stream_status,
        job_store=RecordingJobStore(),
    )
    payment = LeasePayment(
        stream_id=456,
        lease_id="0x" + "11" * 32,
        terms_hash="0x" + "22" * 32,
        rate_per_second_wei=7,
        duration_seconds=3600,
    )

    result = await service.create_vm(
        CreateVMCommand(
            name="vm-a",
            image=None,
            resources=VMResources(cpu=1, memory=1, storage=10),
            ssh_key="ssh-rsa test",
            payment=payment,
            action_signer="0x3333333333333333333333333333333333333333",
            async_mode=False,
        )
    )

    assert isinstance(result, VMInfo)
    assert result.id == "vm-a"
    assert vm_service.create_calls == 1
    assert stream_status.removed == ["vm-a"]


@pytest.mark.asyncio
async def test_failed_create_job_does_not_block_new_stream_create():
    vm_service = ExistingVMService()
    service = VMApplicationService(
        vm_service=vm_service,
        settings={"DEFAULT_VM_IMAGE": "24.04"},
        stream_status_service=FakeStreamStatusService(),
        job_store=FailedCreateJobStore(),
    )
    payment = LeasePayment(
        stream_id=456,
        lease_id="0x" + "11" * 32,
        terms_hash="0x" + "22" * 32,
        rate_per_second_wei=7,
        duration_seconds=3600,
    )

    result = await service.create_vm(
        CreateVMCommand(
            name="vm-a",
            image=None,
            resources=VMResources(cpu=1, memory=1, storage=10),
            ssh_key="ssh-rsa test",
            payment=payment,
            action_signer="0x3333333333333333333333333333333333333333",
            async_mode=False,
        )
    )

    assert isinstance(result, VMInfo)
    assert result.id == "vm-a"
    assert vm_service.create_calls == 1


@pytest.mark.asyncio
async def test_resize_vm_validates_and_maps_replacement_stream():
    stream_status = RecordingStreamStatusService()
    service = VMApplicationService(
        vm_service=LifecycleVMService(),
        settings={"DEFAULT_VM_IMAGE": "24.04"},
        stream_status_service=stream_status,
        job_store=FakeJobStore(),
    )
    resources = VMResources(cpu=2, memory=4, storage=20)
    payment = LeasePayment(
        stream_id=123,
        lease_id="0x" + "11" * 32,
        terms_hash="0x" + "22" * 32,
        rate_per_second_wei=7,
        duration_seconds=3600,
    )

    result = await service.resize_vm(
        "vm-a",
        resources,
        "0x3333333333333333333333333333333333333333",
        payment,
    )

    assert result.resources == resources
    assert stream_status.valid_lease_calls == [
        (
            (payment,),
            {
                "requestor_address": "0x3333333333333333333333333333333333333333",
                "current_vm_id": "vm-a",
                "vm_name": "vm-a",
                "image": "24.04",
                "resources": resources,
            },
        )
    ]
    assert stream_status.set_calls == [
        (("vm-a", 123, "0x3333333333333333333333333333333333333333"), {})
    ]


class LeaseTerminationVMService(LifecycleVMService):
    def __init__(self):
        super().__init__()
        self.deleted = []
        self.stopped = []

    async def delete_vm(self, vm_id: str) -> None:
        self.deleted.append(vm_id)

    async def stop_vm(self, vm_id: str):
        self.stopped.append(vm_id)
        return VMInfo(
            id=vm_id,
            name=vm_id,
            status=VMStatus.STOPPED,
            resources=VMResources(cpu=1, memory=1, storage=10),
        )


class LeaseTerminationStreamStatus:
    def __init__(
        self,
        *,
        chain_terminated=False,
        verify_terminated=True,
        payment_state="expired",
        current_stream_id=123,
    ):
        self.record = {
            "vm_id": "vm-a",
            "stream_id": current_stream_id,
            "requestor_address": "0x3333333333333333333333333333333333333333",
            "state": "active",
            "terminated_by": None,
            "termination_reason": None,
            "terminated_at": None,
            "settlement_tx_hash": None,
            "cleanup_state": None,
        }
        self.chain_terminated = chain_terminated
        self.verify_terminated = verify_terminated
        self.payment_state = payment_state
        self.stream_status_calls = []

    async def is_payment_required(self):
        return True

    async def require_vm_action_authorized(self, vm_id, action_signer):
        return None

    async def verify_vm_stream_terminated(self, vm_id):
        if not self.verify_terminated:
            raise InvalidStreamError("stream is still active")
        return None

    async def terminal_record(self, vm_id):
        return dict(self.record) if self.record["state"] == "terminated" else None

    async def mark_vm_stream_terminated(self, vm_id, **kwargs):
        self.record.update(
            {
                "state": "terminated",
                "terminated_at": "2026-05-14T12:00:00+00:00",
                **kwargs,
            }
        )
        return dict(self.record)

    async def set_vm_stream_cleanup_state(self, vm_id, cleanup_state):
        self.record["cleanup_state"] = cleanup_state
        return dict(self.record)

    async def get_vm_stream_status(self, vm_id):
        self.stream_status_calls.append(vm_id)
        return SimpleNamespace(
            stream_id=self.record["stream_id"],
            payment_state=self.payment_state,
        )

    async def _stream_record(self, vm_id):
        return dict(self.record)

    def _reader(self):
        chain_terminated = self.chain_terminated

        class Reader:
            def get_stream(self, stream_id):
                return {
                    "recipient": (
                        "0x0000000000000000000000000000000000000000"
                        if chain_terminated
                        else "0x2222222222222222222222222222222222222222"
                    )
                }

        return Reader()


class LeaseTerminationClient:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.terminated = []

    def terminate(self, stream_id):
        self.terminated.append(stream_id)
        if self.fail:
            raise RuntimeError("chain down")
        return "0xtx"


@pytest.mark.asyncio
async def test_provider_terminate_lease_submits_chain_before_delete():
    vm_service = LeaseTerminationVMService()
    stream_status = LeaseTerminationStreamStatus()
    client = LeaseTerminationClient()
    service = VMApplicationService(
        vm_service=vm_service,
        settings={},
        stream_status_service=stream_status,
        job_store=FakeJobStore(),
        stream_client=client,
    )

    result = await service.terminate_lease_by_provider("vm-a")

    assert client.terminated == [123]
    assert vm_service.deleted == ["vm-a"]
    assert stream_status.record["state"] == "terminated"
    assert stream_status.record["terminated_by"] == "provider"
    assert stream_status.record["cleanup_state"] == "completed"
    assert result.vm.status == VMStatus.TERMINATED


@pytest.mark.asyncio
async def test_provider_terminate_lease_chain_failure_does_not_delete_vm():
    vm_service = LeaseTerminationVMService()
    stream_status = LeaseTerminationStreamStatus(chain_terminated=False)
    client = LeaseTerminationClient(fail=True)
    service = VMApplicationService(
        vm_service=vm_service,
        settings={},
        stream_status_service=stream_status,
        job_store=FakeJobStore(),
        stream_client=client,
    )

    with pytest.raises(ExternalServiceError):
        await service.terminate_lease_by_provider("vm-a")

    assert vm_service.deleted == []
    assert stream_status.record["state"] == "active"


@pytest.mark.asyncio
async def test_requestor_delete_rejects_active_stream_before_vm_delete():
    vm_service = LeaseTerminationVMService()
    stream_status = LeaseTerminationStreamStatus(verify_terminated=False)
    service = VMApplicationService(
        vm_service=vm_service,
        settings={},
        stream_status_service=stream_status,
        job_store=FakeJobStore(),
    )

    with pytest.raises(InvalidStreamError):
        await service.delete_vm("vm-a", "0x3333333333333333333333333333333333333333")

    assert vm_service.deleted == []
    assert stream_status.record["state"] == "active"


@pytest.mark.asyncio
async def test_expired_lease_cleanup_rechecks_stream_then_deletes_vm():
    vm_service = LeaseTerminationVMService()
    stream_status = LeaseTerminationStreamStatus(payment_state="expired")
    webhooks = CapturingWebhookService()
    service = VMApplicationService(
        vm_service=vm_service,
        settings={},
        stream_status_service=stream_status,
        job_store=FakeJobStore(),
        webhook_service=webhooks,
    )

    result = await service.expire_vm_lease("vm-a", 123)

    assert result is True
    assert stream_status.stream_status_calls == ["vm-a"]
    assert vm_service.stopped == ["vm-a"]
    assert vm_service.deleted == ["vm-a"]
    assert stream_status.record["state"] == "terminated"
    assert stream_status.record["terminated_by"] == "provider"
    assert stream_status.record["termination_reason"] == "stream_expired"
    assert stream_status.record["cleanup_state"] == "completed"
    assert webhooks.events[0][0] == "vm.deleted"


@pytest.mark.asyncio
async def test_expired_lease_cleanup_skips_when_top_up_moved_stream_to_grace():
    vm_service = LeaseTerminationVMService()
    stream_status = LeaseTerminationStreamStatus(payment_state="grace")
    service = VMApplicationService(
        vm_service=vm_service,
        settings={},
        stream_status_service=stream_status,
        job_store=FakeJobStore(),
    )

    result = await service.expire_vm_lease("vm-a", 123)

    assert result is False
    assert stream_status.stream_status_calls == ["vm-a"]
    assert vm_service.stopped == []
    assert vm_service.deleted == []
    assert stream_status.record["state"] == "active"
