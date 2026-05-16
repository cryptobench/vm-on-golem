import asyncio

import pytest

from provider.payments.domain import LeasePayment
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

    with pytest.raises(VMNotFoundError):
        await service.delete_vm("vm-id")

    assert stream_status.removed == ["vm-id"]


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

    async def create_job(self, *args, **kwargs):
        self.created.append((args, kwargs))

    async def update_job(self, *args, **kwargs):
        self.updated.append((args, kwargs))


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
