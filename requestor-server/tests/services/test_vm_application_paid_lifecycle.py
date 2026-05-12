import pytest

from requestor.errors import ExternalServiceError
from requestor.vm.application_service import VMApplicationService
from requestor.vm.domain import VMRecord


class FakeRepo:
    def __init__(self, vm: VMRecord):
        self.vm = vm
        self.deleted = []

    def require(self, name: str) -> VMRecord:
        assert name == self.vm.name
        return self.vm

    def update_status(self, name: str, status: str) -> None:
        assert name == self.vm.name
        self.vm = self.vm.model_copy(update={"status": status})

    def delete(self, name: str) -> None:
        self.deleted.append(name)


class FakeClient:
    def __init__(self):
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def destroy_vm(self, vm_id: str) -> None:
        self.calls.append(("destroy", vm_id))

    async def stop_vm(self, vm_id: str) -> None:
        self.calls.append(("stop", vm_id))


class FakeClientFactory:
    def __init__(self, client: FakeClient):
        self.client = client

    def for_provider_ip(self, provider_ip: str) -> FakeClient:
        return self.client


class FakePaymentService:
    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.terminated = []

    async def terminate_stream(self, stream_id: int):
        self.terminated.append(stream_id)
        if self.fail:
            raise ExternalServiceError("failed to terminate stream")


def make_service(payment_service):
    vm = VMRecord(
        name="vm-name",
        provider_ip="127.0.0.1",
        vm_id="vm-id",
        config={"stream_id": 42},
        status="running",
    )
    repo = FakeRepo(vm)
    client = FakeClient()
    service = VMApplicationService(
        settings=None,
        vm_repo=repo,
        discovery_service=None,
        provider_client_factory=FakeClientFactory(client),
        payment_service=payment_service,
    )
    return service, repo, client


@pytest.mark.asyncio
async def test_delete_paid_vm_terminates_stream_before_provider_delete():
    payment = FakePaymentService()
    service, repo, client = make_service(payment)

    await service.delete_vm("vm-name")

    assert payment.terminated == [42]
    assert client.calls == [("destroy", "vm-id")]
    assert repo.deleted == ["vm-name"]


@pytest.mark.asyncio
async def test_delete_paid_vm_blocks_provider_delete_when_settlement_fails():
    payment = FakePaymentService(fail=True)
    service, repo, client = make_service(payment)

    with pytest.raises(ExternalServiceError):
        await service.delete_vm("vm-name")

    assert payment.terminated == [42]
    assert client.calls == []
    assert repo.deleted == []


@pytest.mark.asyncio
async def test_stop_paid_vm_does_not_terminate_stream():
    payment = FakePaymentService()
    service, repo, client = make_service(payment)

    result = await service.stop_vm("vm-name")

    assert payment.terminated == []
    assert client.calls == [("stop", "vm-id")]
    assert result.status == "stopped"
