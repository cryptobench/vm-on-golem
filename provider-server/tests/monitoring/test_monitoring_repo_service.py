import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from provider.auth.errors import UnauthorizedError
from provider.errors import ValidationError
from provider.monitoring.domain import (
    AlertRule,
    GuestMetricPayload,
    MetricSample,
    MetricScope,
    MetricSource,
)
from provider.monitoring.repo import MonitoringRepository
from provider.monitoring.services import MonitoringService
from provider.vm.models import VMInfo, VMResources, VMStatus


def test_guest_token_auth_and_sample_storage(tmp_path: Path):
    repo = MonitoringRepository(str(tmp_path / "monitoring.sqlite"))
    repo.init_schema()
    token = repo.issue_guest_token("vm-a")
    service = MonitoringService({}, repo, MagicMock(), MagicMock())

    with pytest.raises(UnauthorizedError):
        asyncio_run(
            service.record_guest_sample("vm-a", GuestMetricPayload(token="bad"))
        )

    asyncio_run(
        service.record_guest_sample(
            "vm-a",
            GuestMetricPayload(
                token=token,
                cpu_percent=12.5,
                memory_used_bytes=512,
                memory_total_bytes=1024,
                disk_used_bytes=10,
                disk_total_bytes=100,
            ),
        )
    )
    latest = service.latest()
    guest = latest.vms["vm-a"]["guest_agent"]
    assert guest["cpu_percent"]["value"] == 12.5
    assert guest["memory_percent"]["value"] == 50.0
    assert guest["disk_percent"]["value"] == 10.0


def test_history_range_filters_24h_samples(tmp_path: Path, monkeypatch):
    repo = MonitoringRepository(str(tmp_path / "monitoring.sqlite"))
    repo.init_schema()
    service = MonitoringService({}, repo, MagicMock(), MagicMock())
    now = datetime(2026, 5, 14, 18, 0, tzinfo=timezone.utc)
    monkeypatch.setattr("provider.monitoring.services.utc_now", lambda: now)
    repo.add_samples(
        [
            fixed_vm_sample("cpu_percent", 10, now - timedelta(hours=25)),
            fixed_vm_sample("cpu_percent", 20, now - timedelta(hours=23)),
        ]
    )

    history = service.history(scope=MetricScope.VM, range_name="24h", vm_id="vm-a")

    assert [point.avg for point in history.points] == [20]
    assert history.range == "24h"
    assert history.resolution_seconds == 300


def test_history_aggregates_samples_into_fixed_buckets(tmp_path: Path, monkeypatch):
    repo = MonitoringRepository(str(tmp_path / "monitoring.sqlite"))
    repo.init_schema()
    service = MonitoringService({}, repo, MagicMock(), MagicMock())
    now = datetime(2026, 5, 14, 18, 0, 30, tzinfo=timezone.utc)
    monkeypatch.setattr("provider.monitoring.services.utc_now", lambda: now)
    repo.add_samples(
        [
            fixed_host_sample("cpu_percent", 10, "2026-05-14T18:00:01+00:00"),
            fixed_host_sample("cpu_percent", 20, "2026-05-14T18:00:09+00:00"),
            fixed_host_sample("memory_percent", 50, "2026-05-14T18:00:09+00:00"),
        ]
    )

    history = service.history(scope=MetricScope.HOST, range_name="1h")
    cpu_points = [point for point in history.points if point.metric == "cpu_percent"]
    memory_points = [
        point for point in history.points if point.metric == "memory_percent"
    ]

    assert len(cpu_points) == 1
    assert cpu_points[0].avg == 15
    assert cpu_points[0].min == 10
    assert cpu_points[0].max == 20
    assert cpu_points[0].count == 2
    assert cpu_points[0].bucket_start == datetime(
        2026, 5, 14, 18, 0, tzinfo=timezone.utc
    )
    assert len(memory_points) == 1
    assert memory_points[0].avg == 50


def test_history_keeps_scope_source_metric_and_vm_buckets_separate(
    tmp_path: Path, monkeypatch
):
    repo = MonitoringRepository(str(tmp_path / "monitoring.sqlite"))
    repo.init_schema()
    service = MonitoringService({}, repo, MagicMock(), MagicMock())
    now = datetime(2026, 5, 14, 18, 0, 30, tzinfo=timezone.utc)
    monkeypatch.setattr("provider.monitoring.services.utc_now", lambda: now)
    repo.add_samples(
        [
            fixed_vm_sample("cpu_percent", 10, now - timedelta(seconds=4)),
            fixed_vm_sample("memory_percent", 20, now - timedelta(seconds=4)),
            MetricSample(
                scope=MetricScope.VM,
                source=MetricSource.INFRASTRUCTURE,
                vm_id="vm-a",
                metric="cpu_percent",
                value=30,
                unit="percent",
                timestamp=now - timedelta(seconds=4),
            ),
            MetricSample(
                scope=MetricScope.VM,
                source=MetricSource.GUEST_AGENT,
                vm_id="vm-b",
                metric="cpu_percent",
                value=40,
                unit="percent",
                timestamp=now - timedelta(seconds=4),
            ),
        ]
    )

    history = service.history(scope=MetricScope.VM, range_name="1h")
    keys = {
        (point.source, point.vm_id, point.metric, point.avg) for point in history.points
    }

    assert keys == {
        (MetricSource.GUEST_AGENT, "vm-a", "cpu_percent", 10),
        (MetricSource.GUEST_AGENT, "vm-a", "memory_percent", 20),
        (MetricSource.INFRASTRUCTURE, "vm-a", "cpu_percent", 30),
        (MetricSource.GUEST_AGENT, "vm-b", "cpu_percent", 40),
    }


@pytest.mark.parametrize(
    ("range_name", "resolution_seconds"),
    [
        ("1h", 10),
        ("6h", 60),
        ("24h", 300),
        ("7d", 3600),
        ("30d", 21600),
    ],
)
def test_history_returns_expected_resolution(
    tmp_path: Path, range_name: str, resolution_seconds: int
):
    repo = MonitoringRepository(str(tmp_path / "monitoring.sqlite"))
    repo.init_schema()
    service = MonitoringService({}, repo, MagicMock(), MagicMock())

    history = service.history(scope=MetricScope.HOST, range_name=range_name)

    assert history.range == range_name
    assert history.resolution_seconds == resolution_seconds


def test_history_rejects_invalid_range(tmp_path: Path):
    repo = MonitoringRepository(str(tmp_path / "monitoring.sqlite"))
    repo.init_schema()
    service = MonitoringService({}, repo, MagicMock(), MagicMock())

    with pytest.raises(ValidationError, match="invalid metrics history range"):
        service.history(scope=MetricScope.VM, range_name="bogus", vm_id="vm-a")


def test_guest_samples_use_live_cache_and_downsample_history(tmp_path: Path):
    repo = MonitoringRepository(str(tmp_path / "monitoring.sqlite"))
    repo.init_schema()
    token = repo.issue_guest_token("vm-a")
    service = MonitoringService(
        {
            "MONITORING_LIVE_ACTIVE_INTERVAL_SECONDS": 1,
            "MONITORING_LIVE_IDLE_INTERVAL_SECONDS": 30,
            "MONITORING_HISTORY_DOWNSAMPLE_SECONDS": 10,
        },
        repo,
        MagicMock(),
        MagicMock(),
    )

    async def _record_live_samples():
        async with service.watch_vm("vm-a"):
            first_result = await service.record_guest_sample(
                "vm-a",
                GuestMetricPayload(token=token, cpu_percent=10),
            )
            second_result = await service.record_guest_sample(
                "vm-a",
                GuestMetricPayload(token=token, cpu_percent=20),
            )
            return first_result, second_result

    first, second = asyncio_run(_record_live_samples())

    latest = service.latest()
    assert latest.vms["vm-a"]["guest_agent"]["cpu_percent"]["value"] == 20
    assert first.next_interval_seconds == 1
    assert second.live_mode is True
    persisted_cpu = [
        sample
        for sample in repo.history(
            MetricScope.VM, since=latest.generated_at.replace(year=2000)
        )
        if sample.metric == "cpu_percent"
    ]
    assert len(persisted_cpu) == 1


def test_infrastructure_collection_uses_list_status_not_guest_exec(tmp_path: Path):
    repo = MonitoringRepository(str(tmp_path / "monitoring.sqlite"))
    repo.init_schema()
    vm_service = MagicMock()
    vm_service.list_vms = AsyncMock(
        return_value=[
            VMInfo(
                id="vm-a",
                name="vm-a",
                status=VMStatus.RUNNING,
                resources=VMResources(cpu=1, memory=1, storage=10),
            )
        ]
    )
    proxy = MagicMock()
    proxy.get_traffic_counters.return_value = {
        "vm-a": {"rx_bytes": 10, "tx_bytes": 20, "connections": 1}
    }
    service = MonitoringService({}, repo, vm_service, proxy)

    samples = asyncio_run(service._collect_samples())

    assert any(sample.metric == "allocated_cpu" for sample in samples)
    vm_service.list_vms.assert_awaited_once()
    assert vm_service.method_calls == [("list_vms", (), {})]


def test_host_live_samples_update_latest_and_downsample_history(tmp_path: Path):
    repo = MonitoringRepository(str(tmp_path / "monitoring.sqlite"))
    repo.init_schema()
    service = MonitoringService(
        {"MONITORING_HISTORY_DOWNSAMPLE_SECONDS": 10},
        repo,
        MagicMock(),
        MagicMock(),
    )
    first = fixed_host_sample("cpu_percent", 10, "2026-05-14T18:00:00+00:00")
    second = fixed_host_sample("cpu_percent", 20, "2026-05-14T18:00:01+00:00")
    service._host_samples = MagicMock(side_effect=[[first], [second]])

    asyncio_run(service.record_host_live_sample(first.timestamp))
    asyncio_run(service.record_host_live_sample(second.timestamp))

    latest = service.latest()
    assert latest.host["cpu_percent"]["value"] == 20
    persisted = repo.history(MetricScope.HOST, since=first.timestamp.replace(year=2020))
    assert [sample.value for sample in persisted] == [10]


def test_host_metrics_subscriber_receives_update(tmp_path: Path):
    async def run():
        repo = MonitoringRepository(str(tmp_path / "monitoring.sqlite"))
        repo.init_schema()
        service = MonitoringService({}, repo, MagicMock(), MagicMock())
        sample = fixed_host_sample("cpu_percent", 42, "2026-05-14T18:00:00+00:00")
        service._host_samples = MagicMock(return_value=[sample])

        async with service.subscribe_host_metrics() as queue:
            await service.record_host_live_sample(sample.timestamp)
            payload = await asyncio.wait_for(queue.get(), timeout=1)

        assert payload["latest"]["host"]["cpu_percent"]["value"] == 42
        assert has_explicit_timezone(payload["latest"]["generated_at"])
        assert payload["samples"][0]["scope"] == "host"
        assert has_explicit_timezone(payload["samples"][0]["timestamp"])

    asyncio_run(run())


def test_host_disk_path_prefers_existing_parent_and_windows_drive(tmp_path: Path):
    repo = MonitoringRepository(str(tmp_path / "monitoring.sqlite"))
    service = MonitoringService(
        {"VM_DATA_DIR": str(tmp_path / "missing" / "child")},
        repo,
        MagicMock(),
        MagicMock(),
    )

    assert service._host_disk_path() == str(tmp_path)

    windows_service = MonitoringService(
        {"VM_DATA_DIR": "C:\\golem\\provider\\vms"},
        repo,
        MagicMock(),
        MagicMock(),
    )
    assert windows_service._host_disk_path() == "C:\\"


def test_alert_evaluation_emits_webhook_events(tmp_path: Path):
    class FakeWebhookService:
        def __init__(self):
            self.events = []

        async def emit_event(self, event):
            self.events.append(event)

    repo = MonitoringRepository(str(tmp_path / "monitoring.sqlite"))
    repo.init_schema()
    rule = repo.create_alert_rule(
        AlertRule(
            name="Host CPU high",
            metric="cpu_percent",
            scope=MetricScope.HOST,
            source=MetricSource.INFRASTRUCTURE,
            threshold=80,
            duration_seconds=0,
            severity="critical",
        )
    )
    webhook_service = FakeWebhookService()
    service = MonitoringService(
        {},
        repo,
        MagicMock(),
        MagicMock(),
        webhook_service=webhook_service,
    )
    now = datetime(2026, 5, 14, 18, 0, tzinfo=timezone.utc)
    repo.add_samples([fixed_host_sample(rule.metric, 90, now.isoformat())])

    asyncio_run(service._evaluate_alerts())

    repo.add_samples(
        [fixed_host_sample(rule.metric, 20, (now + timedelta(seconds=1)).isoformat())]
    )
    asyncio_run(service._evaluate_alerts())

    assert [event.event_type for event in webhook_service.events] == [
        "alert.fired",
        "alert.resolved",
    ]
    assert webhook_service.events[0].severity == "critical"
    assert webhook_service.events[0].data["metric"] == "cpu_percent"


def asyncio_run(coro):
    import asyncio

    return asyncio.run(coro)


def fixed_host_sample(metric: str, value: float, timestamp: str) -> MetricSample:
    return MetricSample(
        scope=MetricScope.HOST,
        source=MetricSource.INFRASTRUCTURE,
        metric=metric,
        value=value,
        unit="percent",
        timestamp=datetime.fromisoformat(timestamp),
    )


def fixed_vm_sample(metric: str, value: float, timestamp: datetime) -> MetricSample:
    return MetricSample(
        scope=MetricScope.VM,
        source=MetricSource.GUEST_AGENT,
        vm_id="vm-a",
        metric=metric,
        value=value,
        unit="percent",
        timestamp=timestamp,
    )


def has_explicit_timezone(value: str) -> bool:
    return value.endswith("Z") or value.endswith("+00:00")
