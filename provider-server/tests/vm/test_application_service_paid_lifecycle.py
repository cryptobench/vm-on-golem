import pytest

from provider.vm.application_service import VMApplicationService
from provider.vm.models import VMNotFoundError


class FakeVMService:
    async def delete_vm(self, vm_id: str) -> None:
        raise VMNotFoundError(f"VM {vm_id} not found")


class FakeStreamStatusService:
    def __init__(self):
        self.removed = []

    async def remove_vm_stream(self, vm_id: str) -> None:
        self.removed.append(vm_id)


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
