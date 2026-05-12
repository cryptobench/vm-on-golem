import asyncio
from pathlib import Path
from unittest.mock import MagicMock

from provider.live.service import VMLiveService
from provider.monitoring.domain import GuestMetricPayload
from provider.monitoring.repo import MonitoringRepository
from provider.monitoring.services import MonitoringService
from provider.payments.errors import StreamNotFoundError
from provider.provider_info.domain import ProviderInfo
from provider.vm.models import VMAccessInfo, VMInfo, VMResources, VMStatus


class FakeWebSocket:
    def __init__(self):
        self.accepted = False
        self.sent: asyncio.Queue[dict] = asyncio.Queue()

    async def accept(self):
        self.accepted = True

    async def send_json(self, payload):
        await self.sent.put(payload)

    async def receive_json(self):
        await asyncio.Future()


class FakeVmApp:
    async def get_vm_status(self, vm_id):
        return VMInfo(
            id=vm_id,
            name=vm_id,
            status=VMStatus.RUNNING,
            resources=VMResources(cpu=1, memory=1, storage=10),
        )

    async def get_vm_access(self, vm_id):
        return VMAccessInfo(
            ssh_host="127.0.0.1",
            ssh_port=50800,
            ssh_user="ubuntu",
            vm_id=vm_id,
            multipass_name=vm_id,
        )

    async def list_snapshots(self, vm_id):
        return []


class FakeProviderInfo:
    def get_info(self):
        return ProviderInfo(
            provider_id="provider-a",
            stream_payment_address="0x0000000000000000000000000000000000000000",
            glm_token_address="0x0000000000000000000000000000000000000000",
            eth_token_address="0x0000000000000000000000000000000000000000",
            ip_address="127.0.0.1",
            country="SE",
            platform="arm64",
        )


class FakeStreamStatus:
    async def get_vm_stream_status(self, vm_id):
        raise StreamNotFoundError("no stream mapped for this VM")


def test_vm_live_stream_sends_hello_snapshot_and_metric_update(tmp_path: Path):
    async def run():
        repo = MonitoringRepository(str(tmp_path / "monitoring.sqlite"))
        repo.init_schema()
        token = repo.issue_guest_token("vm-a")
        monitoring = MonitoringService(
            {"MONITORING_LIVE_ACTIVE_INTERVAL_SECONDS": 1},
            repo,
            MagicMock(),
            MagicMock(),
        )
        service = VMLiveService(
            monitoring,
            FakeVmApp(),
            FakeProviderInfo(),
            FakeStreamStatus(),
        )
        websocket = FakeWebSocket()
        task = asyncio.create_task(service.stream_vm(websocket, "vm-a"))
        try:
            hello = await asyncio.wait_for(websocket.sent.get(), timeout=1)
            snapshot = await asyncio.wait_for(websocket.sent.get(), timeout=1)
            await monitoring.record_guest_sample(
                "vm-a", GuestMetricPayload(token=token, cpu_percent=42)
            )
            update = await asyncio.wait_for(websocket.sent.get(), timeout=1)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

        assert websocket.accepted is True
        assert hello["type"] == "hello"
        assert snapshot["type"] == "snapshot"
        assert update["type"] == "update"
        assert update["scope"] == "metrics"
        assert (
            update["data"]["latest"]["vms"]["vm-a"]["guest_agent"]["cpu_percent"][
                "value"
            ]
            == 42
        )

    asyncio.run(run())
