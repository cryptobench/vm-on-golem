import pytest
from unittest.mock import AsyncMock, MagicMock

from requestor.services.vm_service import VMService
from requestor.services.database_service import DatabaseService
from requestor.services.ssh_service import SSHService
from requestor.provider.client import ProviderClient
from requestor.errors import VMError


@pytest.mark.asyncio
async def test_stop_vm_updates_status(tmp_path):
    db_path = tmp_path / "test.db"
    db_service = DatabaseService(db_path)
    await db_service.init()
    await db_service.save_vm(
        name="test-vm",
        provider_ip="127.0.0.1",
        vm_id="vm-id-123",
        config={"cpu": 1, "memory": 1, "storage": 10, "ssh_port": 2222},
    )

    provider_client = MagicMock(spec=ProviderClient)
    provider_client.stop_vm = AsyncMock()
    ssh_service = MagicMock(spec=SSHService)

    vm_service = VMService(db_service, ssh_service, provider_client)
    await vm_service.stop_vm("test-vm")

    provider_client.stop_vm.assert_awaited_once_with("vm-id-123")
    vm = await db_service.get_vm("test-vm")
    assert vm["status"] == "stopped"


@pytest.mark.asyncio
async def test_stop_vm_not_found(tmp_path):
    db_path = tmp_path / "test.db"
    db_service = DatabaseService(db_path)
    await db_service.init()

    provider_client = MagicMock(spec=ProviderClient)
    provider_client.stop_vm = AsyncMock()
    ssh_service = MagicMock(spec=SSHService)

    vm_service = VMService(db_service, ssh_service, provider_client)

    with pytest.raises(VMError):
        await vm_service.stop_vm("missing-vm")
    provider_client.stop_vm.assert_not_awaited()
