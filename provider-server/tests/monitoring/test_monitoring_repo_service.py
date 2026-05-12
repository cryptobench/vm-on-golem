from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from provider.monitoring.domain import GuestMetricPayload, MetricScope, MetricSource
from provider.monitoring.repo import MonitoringRepository
from provider.monitoring.services import MonitoringService
from provider.vm.models import VMInfo, VMResources, VMStatus


def test_guest_token_auth_and_sample_storage(tmp_path: Path):
    repo = MonitoringRepository(str(tmp_path / "monitoring.sqlite"))
    repo.init_schema()
    token = repo.issue_guest_token("vm-a")
    service = MonitoringService({}, repo, MagicMock(), MagicMock())

    with pytest.raises(ValueError):
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


def asyncio_run(coro):
    import asyncio

    return asyncio.run(coro)
