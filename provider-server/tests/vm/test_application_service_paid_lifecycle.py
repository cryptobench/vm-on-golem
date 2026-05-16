import pytest

from provider.summary.service import ProviderSummaryService
from provider.vm.application_service import VMApplicationService
from provider.vm.models import VMNotFoundError, VMResources


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
