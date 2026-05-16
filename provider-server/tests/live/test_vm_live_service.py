import asyncio
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

from fastapi import WebSocketDisconnect

from provider.live.events import ProviderEventBroadcaster
from provider.live.service import HostLiveService, ProviderLiveService, VMLiveService
from provider.monitoring.domain import (
    GuestMetricPayload,
    MetricSample,
    MetricScope,
    MetricsHistoryResponse,
    MetricSource,
)
from provider.monitoring.repo import MonitoringRepository
from provider.monitoring.services import MonitoringService
from provider.payments.errors import StreamNotFoundError
from provider.provider_info.domain import ProviderInfo
from provider.vm.models import VMAccessInfo, VMInfo, VMResources, VMStatus


def empty_history(range_name: str = "1h") -> MetricsHistoryResponse:
    return MetricsHistoryResponse(
        points=[],
        range=range_name,
        resolution_seconds=10,
        generated_at=datetime(2026, 5, 14, tzinfo=timezone.utc),
    )


class FakeWebSocket:
    def __init__(self):
        self.accepted = False
        self.closed_code = None
        self.sent: asyncio.Queue[dict] = asyncio.Queue()
        self.received: asyncio.Queue[dict] = asyncio.Queue()
        self.received.put_nowait({"type": "auth", "token": "test-token"})

    async def accept(self):
        self.accepted = True

    async def send_json(self, payload):
        await self.sent.put(payload)

    async def receive_json(self):
        return await self.received.get()

    async def close(self, code=1000):
        self.closed_code = code


class DisconnectingWebSocket(FakeWebSocket):
    async def send_json(self, payload):
        raise WebSocketDisconnect()


class BadAuthWebSocket(FakeWebSocket):
    def __init__(self):
        super().__init__()
        self.received = asyncio.Queue()
        self.received.put_nowait({"type": "refresh"})


class FakeVmApp:
    async def list_vms(self):
        return [await self.get_vm_status("vm-a")]

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
    async def list_stream_statuses(self):
        return []

    async def get_vm_stream_status(self, vm_id):
        raise StreamNotFoundError("no stream mapped for this VM")


class FakeAuth:
    def validate_requestor_token(self, token):
        return object()

    async def require_vm_access(self, identity, vm_id):
        return identity

    def validate_admin_token(self, token):
        return object()


class FakeSummary:
    async def get_summary(self):
        from provider.summary.domain import ProviderSummary

        return ProviderSummary(
            status="running",
            resources={"total": {}, "available": {}},
            pricing={},
            vms=[],
            env={},
        )


class FailingSummary:
    async def get_summary(self):
        raise RuntimeError("summary unavailable")


class FakeMonitoring:
    async def overview(self):
        from provider.monitoring.domain import MonitoringOverview

        return MonitoringOverview(
            status="healthy",
            host={},
            vms=[],
            active_alerts=[],
        )

    def latest(self):
        from provider.monitoring.domain import MetricsLatestResponse

        return MetricsLatestResponse(
            host={},
            vms={},
            generated_at=datetime(2026, 5, 14, tzinfo=timezone.utc),
        )

    def history(self, **kwargs):
        return empty_history(kwargs.get("range_name", "1h"))

    def active_alerts(self):
        return []

    def list_alert_rules(self):
        return []

    def list_webhooks(self):
        return []


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
            FakeAuth(),
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
        assert "points" in snapshot["data"]["metrics_history"]
        assert snapshot["data"]["metrics_history"]["resolution_seconds"] == 10
        assert update["type"] == "update"
        assert update["scope"] == "metrics"
        assert (
            update["data"]["latest"]["vms"]["vm-a"]["guest_agent"]["cpu_percent"][
                "value"
            ]
            == 42
        )

    asyncio.run(run())


def test_vm_live_stream_sends_no_snapshot_before_auth():
    async def run():
        service = VMLiveService(
            MagicMock(),
            FakeVmApp(),
            FakeProviderInfo(),
            FakeStreamStatus(),
            FakeAuth(),
        )
        websocket = BadAuthWebSocket()

        await service.stream_vm(websocket, "vm-a")

        event = await asyncio.wait_for(websocket.sent.get(), timeout=1)
        assert websocket.accepted is True
        assert event["type"] == "error"
        assert websocket.closed_code == 1008
        assert websocket.sent.empty()

    asyncio.run(run())


def test_vm_live_stream_treats_early_disconnect_as_normal_close(tmp_path: Path):
    async def run():
        repo = MonitoringRepository(str(tmp_path / "monitoring.sqlite"))
        repo.init_schema()
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
            FakeAuth(),
        )
        websocket = DisconnectingWebSocket()

        await asyncio.wait_for(service.stream_vm(websocket, "vm-a"), timeout=1)

        assert websocket.accepted is True

    asyncio.run(run())


def test_vm_live_stream_rejects_invalid_initial_history_range():
    async def run():
        service = VMLiveService(
            MagicMock(),
            FakeVmApp(),
            FakeProviderInfo(),
            FakeStreamStatus(),
            FakeAuth(),
        )
        websocket = FakeWebSocket()

        await service.stream_vm(websocket, "vm-a", history_range="bogus")

        event = await asyncio.wait_for(websocket.sent.get(), timeout=1)
        assert websocket.accepted is True
        assert event["type"] == "error"
        assert event["scope"] == "metrics"
        assert "invalid metrics history range" in event["error"]
        assert websocket.closed_code == 1008
        assert websocket.sent.empty()

    asyncio.run(run())


def test_vm_live_invalid_history_range_event_keeps_current_range(tmp_path: Path):
    async def run():
        repo = MonitoringRepository(str(tmp_path / "monitoring.sqlite"))
        repo.init_schema()
        monitoring = MonitoringService(
            {"MONITORING_LIVE_ACTIVE_INTERVAL_SECONDS": 1},
            repo,
            MagicMock(),
            MagicMock(),
        )
        history_ranges: list[str] = []

        def history(**kwargs):
            history_ranges.append(kwargs["range_name"])
            return empty_history(kwargs["range_name"])

        monitoring.history = MagicMock(side_effect=history)
        service = VMLiveService(
            monitoring,
            FakeVmApp(),
            FakeProviderInfo(),
            FakeStreamStatus(),
            FakeAuth(),
        )
        websocket = FakeWebSocket()
        task = asyncio.create_task(service.stream_vm(websocket, "vm-a"))
        try:
            await asyncio.wait_for(websocket.sent.get(), timeout=1)
            snapshot = await asyncio.wait_for(websocket.sent.get(), timeout=1)
            assert snapshot["type"] == "snapshot"
            assert history_ranges == ["1h"]

            await websocket.received.put(
                {"type": "set_history_range", "history_range": "bogus"}
            )
            error = await asyncio.wait_for(websocket.sent.get(), timeout=1)
            assert error["type"] == "error"
            assert error["scope"] == "metrics"
            assert "invalid metrics history range" in error["error"]
            assert history_ranges == ["1h"]

            await websocket.received.put({"type": "refresh", "scopes": ["metrics"]})
            update = await asyncio.wait_for(websocket.sent.get(), timeout=1)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

        assert update["type"] == "update"
        assert update["scope"] == "metrics"
        assert history_ranges == ["1h", "1h"]

    asyncio.run(run())


def test_host_live_stream_sends_hello_snapshot_and_metric_update(tmp_path: Path):
    async def run():
        repo = MonitoringRepository(str(tmp_path / "monitoring.sqlite"))
        repo.init_schema()
        monitoring = MonitoringService(
            {"MONITORING_LIVE_ACTIVE_INTERVAL_SECONDS": 1},
            repo,
            MagicMock(),
            MagicMock(),
        )
        monitoring._host_samples = MagicMock(
            return_value=[
                MetricSample(
                    scope=MetricScope.HOST,
                    source=MetricSource.INFRASTRUCTURE,
                    metric="cpu_percent",
                    value=42,
                    unit="percent",
                    timestamp=datetime_fromisoformat("2026-05-14T18:00:00+00:00"),
                )
            ]
        )
        service = HostLiveService(monitoring, FakeAuth())
        websocket = FakeWebSocket()
        task = asyncio.create_task(service.stream_host(websocket))
        try:
            hello = await asyncio.wait_for(websocket.sent.get(), timeout=1)
            snapshot = await asyncio.wait_for(websocket.sent.get(), timeout=1)
            update = await asyncio.wait_for(websocket.sent.get(), timeout=1)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

        assert websocket.accepted is True
        assert hello["type"] == "hello"
        assert hello["data"]["protocol"] == "provider-host-live.v1"
        assert snapshot["type"] == "snapshot"
        assert "points" in snapshot["data"]["metrics_history"]
        assert snapshot["data"]["metrics_history"]["resolution_seconds"] == 10
        assert update["type"] == "update"
        assert update["scope"] == "metrics"
        assert update["data"]["latest"]["host"]["cpu_percent"]["value"] == 42
        assert has_explicit_timezone(update["data"]["samples"][0]["timestamp"])

    asyncio.run(run())


def test_provider_live_stream_sends_snapshot_and_invalidation_update():
    async def run():
        broadcaster = ProviderEventBroadcaster()
        service = ProviderLiveService(
            broadcaster=broadcaster,
            provider_info_service=FakeProviderInfo(),
            summary_service=FakeSummary(),
            vm_application_service=FakeVmApp(),
            stream_status_service=FakeStreamStatus(),
            monitoring_service=FakeMonitoring(),
            auth_service=FakeAuth(),
        )
        websocket = FakeWebSocket()
        task = asyncio.create_task(service.stream_provider(websocket))
        try:
            hello = await asyncio.wait_for(websocket.sent.get(), timeout=1)
            snapshot = await asyncio.wait_for(websocket.sent.get(), timeout=1)
            await broadcaster.publish(["vms"])
            update = await asyncio.wait_for(websocket.sent.get(), timeout=1)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

        assert websocket.accepted is True
        assert hello["data"]["protocol"] == "provider-live.v1"
        assert snapshot["type"] == "snapshot"
        assert snapshot["data"]["vms"][0]["id"] == "vm-a"
        assert update["type"] == "update"
        assert update["scope"] == "vms"
        assert update["data"]["vms"][0]["status"] == "running"

    asyncio.run(run())


def test_provider_live_stream_sends_scoped_error():
    async def run():
        service = ProviderLiveService(
            broadcaster=ProviderEventBroadcaster(),
            provider_info_service=FakeProviderInfo(),
            summary_service=FailingSummary(),
            vm_application_service=FakeVmApp(),
            stream_status_service=FakeStreamStatus(),
            monitoring_service=FakeMonitoring(),
            auth_service=FakeAuth(),
        )
        websocket = FakeWebSocket()
        task = asyncio.create_task(service.stream_provider(websocket))
        try:
            await asyncio.wait_for(websocket.sent.get(), timeout=1)
            await asyncio.wait_for(websocket.sent.get(), timeout=1)
            await websocket.received.put({"type": "refresh", "scopes": ["summary"]})
            event = await asyncio.wait_for(websocket.sent.get(), timeout=1)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

        assert event["type"] == "error"
        assert event["scope"] == "summary"
        assert event["error"] == "summary unavailable"

    asyncio.run(run())


def datetime_fromisoformat(value: str):
    from datetime import datetime

    return datetime.fromisoformat(value)


def has_explicit_timezone(value: str) -> bool:
    return value.endswith("Z") or value.endswith("+00:00")
