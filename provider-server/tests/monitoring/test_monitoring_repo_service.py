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
