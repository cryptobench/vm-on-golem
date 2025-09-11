import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from provider.vm.multipass_adapter import MultipassAdapter, MultipassError
from provider.vm.models import VMConfig, VMResources, VMNotFoundError, VMInfo, VMStatus

@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.MULTIPASS_BINARY_PATH = "/usr/local/bin/multipass"
    return settings

@pytest.fixture
def multipass_adapter(mock_settings):
    with patch('provider.vm.multipass_adapter.settings', mock_settings):
        proxy_manager = AsyncMock()
        proxy_manager.add_vm = AsyncMock(return_value=True)
        proxy_manager.remove_vm = AsyncMock()
        proxy_manager.get_port = MagicMock(return_value=2222)

        name_mapper = AsyncMock()
        name_mapper.add_mapping = AsyncMock()
        name_mapper.get_multipass_name = AsyncMock(return_value="multipass-vm-name")
        name_mapper.get_requestor_name = AsyncMock(return_value="test-vm")
        name_mapper.remove_mapping = AsyncMock()
        name_mapper.list_mappings = MagicMock(return_value={"test-vm": "multipass-vm-name"})

        adapter = MultipassAdapter(proxy_manager, name_mapper)
        adapter._run_multipass = AsyncMock()
        return adapter

@pytest.mark.asyncio
async def test_verify_installation_success(multipass_adapter):
    # Arrange
    mock_process = MagicMock()
    mock_process.stdout = "multipass 1.13.1+mac"
    multipass_adapter._run_multipass.return_value = mock_process

    # Act & Assert
    try:
        await multipass_adapter.initialize()
    except MultipassError:
        pytest.fail("MultipassError was raised unexpectedly")

@pytest.mark.asyncio
async def test_verify_installation_failure(multipass_adapter):
    # Arrange
    multipass_adapter._run_multipass.side_effect = MultipassError("Command failed")

    # Act & Assert
    with pytest.raises(MultipassError):
        await multipass_adapter.initialize()

@pytest.mark.asyncio
async def test_create_vm_happy_path(multipass_adapter):
    # Arrange
    config = VMConfig(
        name="test-vm",
        image="ubuntu:22.04",
        ssh_key="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQD...",
        cloud_init_path="/path/to/cloud-init",
        resources=VMResources(cpu=2, memory=2, storage=20)
    )
    
    multipass_adapter._get_vm_info = AsyncMock(return_value={
        "state": "RUNNING",
        "ipv4": ["127.0.0.1"],
        "cpu_count": "2",
        "memory": {"total": 2147483648},
        "disks": {"sda1": {"total": 21474836480}}
    })

    # Act
    await multipass_adapter.create_vm(config)

    # Assert
    multipass_adapter._run_multipass.assert_called()
    launch_call_args = multipass_adapter._run_multipass.call_args[0][0]
    assert launch_call_args[0] == "launch"
    assert launch_call_args[1] == config.image
    assert launch_call_args[2] == "--name"
    assert launch_call_args[3].startswith("golem-")
    multipass_adapter.name_mapper.add_mapping.assert_awaited_once()

@pytest.mark.asyncio
async def test_create_vm_multipass_fails(multipass_adapter):
    # Arrange
    config = VMConfig(
        name="test-vm",
        image="ubuntu:22.04",
        ssh_key="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQD...",
        cloud_init_path="/path/to/cloud-init",
        resources=VMResources(cpu=2, memory=2, storage=20)
    )
    multipass_adapter._run_multipass.side_effect = MultipassError("Multipass command failed")
    multipass_adapter.proxy_manager.remove_vm = AsyncMock()

    # Act & Assert
    with pytest.raises(MultipassError):
        await multipass_adapter.create_vm(config)

@pytest.mark.asyncio
async def test_delete_vm_happy_path(multipass_adapter):
    # Arrange
    multipass_adapter.name_mapper.get_requestor_name = AsyncMock(return_value="test-vm")


    # Act
    await multipass_adapter.delete_vm("test-vm")

    # Assert
    multipass_adapter._run_multipass.assert_called_once_with(["delete", "test-vm", "--purge"], check=False)
    multipass_adapter.name_mapper.remove_mapping.assert_awaited_once_with("test-vm")

@pytest.mark.asyncio
async def test_delete_vm_does_not_exist(multipass_adapter):
    # Arrange
    multipass_adapter.name_mapper.get_requestor_name = AsyncMock(return_value=None)

    # Act
    await multipass_adapter.delete_vm("test-vm")

    # Assert
    multipass_adapter._run_multipass.assert_called_once_with(["delete", "test-vm", "--purge"], check=False)
    multipass_adapter.name_mapper.remove_mapping.assert_not_awaited()

@pytest.mark.asyncio
async def test_get_vm_status_happy_path(multipass_adapter):
    # Arrange
    multipass_adapter._get_vm_info = AsyncMock(return_value={
        "state": "RUNNING",
        "ipv4": ["192.168.64.2"],
        "cpu_count": "2",
        "memory": {"total": 2147483648},
        "disks": {"sda1": {"total": 10737418240}}
    })


    # Act
    status = await multipass_adapter.get_vm_status("test-vm")

    # Assert
    assert status.status.value == "running"
    assert status.ip_address == "192.168.64.2"
    assert status.ssh_port == 2222
    assert status.resources.cpu == 2
    assert status.resources.memory == 2
    assert status.resources.storage == 10

@pytest.mark.asyncio
async def test_get_vm_status_vm_not_found(multipass_adapter):
    # Arrange
    multipass_adapter._get_vm_info = AsyncMock(side_effect=MultipassError("VM not found"))

    # Act & Assert
    with pytest.raises(VMNotFoundError):
        await multipass_adapter.get_vm_status("non-existent-vm")

@pytest.mark.asyncio
async def test_create_vm_get_status_fails(multipass_adapter):
    # Arrange
    config = VMConfig(
        name="test-vm",
        image="ubuntu:22.04",
        ssh_key="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQD...",
        cloud_init_path="/path/to/cloud-init",
        resources=VMResources(cpu=2, memory=2, storage=20)
    )
    multipass_adapter._get_vm_info = AsyncMock(side_effect=MultipassError("VM not found"))

    # Act & Assert
    with pytest.raises(MultipassError):
        await multipass_adapter.create_vm(config)

@pytest.mark.asyncio
async def test_delete_vm_multipass_fails(multipass_adapter):
    # Arrange
    multipass_adapter.name_mapper.get_requestor_name = AsyncMock(return_value="test-vm")
    multipass_adapter._run_multipass.side_effect = MultipassError("Multipass command failed")

    # Act & Assert
    with pytest.raises(MultipassError):
        await multipass_adapter.delete_vm("test-vm")

@pytest.mark.asyncio
async def test_get_vm_status_not_running(multipass_adapter):
    # Arrange
    multipass_adapter._get_vm_info = AsyncMock(return_value={
        "state": "STOPPED",
        "ipv4": [],
        "cpu_count": "2",
        "memory": {"total": 2147483648},
        "disks": {"sda1": {"total": 10737418240}}
    })

    # Act
    status = await multipass_adapter.get_vm_status("test-vm")

    # Assert
    assert status.status.value == "stopped"
    assert status.ip_address is None

@pytest.mark.asyncio
async def test_get_vm_status_no_ipv4(multipass_adapter):
    # Arrange
    multipass_adapter._get_vm_info = AsyncMock(return_value={
        "state": "RUNNING",
        "ipv4": [],
        "cpu_count": "2",
        "memory": {"total": 2147483648},
        "disks": {"sda1": {"total": 10737418240}}
    })

    # Act
    status = await multipass_adapter.get_vm_status("test-vm")

    # Assert
    assert status.status.value == "running"
    assert status.ip_address is None

import subprocess

@pytest.mark.asyncio
async def test_parse_vm_info_missing_fields(multipass_adapter):
    # Arrange
    mock_process = MagicMock()
    mock_process.stdout = '{"info": {"test-vm": {"state": "RUNNING"}}}'  # Missing fields
    multipass_adapter._run_multipass.return_value = mock_process

    # Act & Assert
    with pytest.raises(MultipassError):
        await multipass_adapter._get_vm_info("test-vm")

from pydantic import ValidationError

@pytest.mark.parametrize("resources_data, expected_error", [
    ({"cpu": 0, "memory": 2, "storage": 20}, "Input should be greater than or equal to 1"),
    ({"cpu": 2, "memory": 0, "storage": 20}, "Input should be greater than or equal to 1"),
    ({"cpu": 2, "memory": 2, "storage": 9}, "Input should be greater than or equal to 10"),
])
def test_vm_resources_validation(resources_data, expected_error):
    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        VMResources(**resources_data)
    assert expected_error in str(exc_info.value)

@pytest.mark.asyncio
async def test_start_vm(multipass_adapter):
    # Arrange
    multipass_adapter.get_vm_status = AsyncMock()

    # Act
    await multipass_adapter.start_vm("test-vm")

    # Assert
    multipass_adapter._run_multipass.assert_awaited_once_with(["start", "test-vm"])
    multipass_adapter.get_vm_status.assert_awaited_once_with("test-vm")

@pytest.mark.asyncio
async def test_stop_vm(multipass_adapter):
    # Arrange
    multipass_adapter.get_vm_status = AsyncMock()

    # Act
    await multipass_adapter.stop_vm("test-vm")

    # Assert
    multipass_adapter._run_multipass.assert_awaited_once_with(["stop", "test-vm"])
    multipass_adapter.get_vm_status.assert_awaited_once_with("test-vm")

@pytest.mark.asyncio
async def test_list_vms(multipass_adapter):
    # Arrange
    multipass_adapter.get_vm_status = AsyncMock(return_value=MagicMock(spec=VMInfo))

    # Act
    vms = await multipass_adapter.list_vms()

    # Assert
    assert len(vms) == 1
    multipass_adapter.get_vm_status.assert_awaited_once_with("test-vm")

@pytest.mark.asyncio
async def test_get_all_vms_resources(multipass_adapter):
    # Arrange
    multipass_adapter._get_vm_info = AsyncMock(return_value={
        "state": "RUNNING",
        "ipv4": ["192.168.64.2"],
        "cpu_count": "2",
        "memory": {"total": 2147483648},
        "disks": {"sda1": {"total": 10737418240}}
    })

    # Act
    resources = await multipass_adapter.get_all_vms_resources()

    # Assert
    assert "test-vm" in resources
    assert resources["test-vm"].cpu == 2
    assert resources["test-vm"].memory == 2
    assert resources["test-vm"].storage == 10


@pytest.mark.asyncio
async def test_get_vm_status_handles_empty_numeric_fields(multipass_adapter):
    # Arrange: simulate multipass returning empty strings/objects for numeric fields when stopped
    multipass_adapter._get_vm_info = AsyncMock(return_value={
        "state": "STOPPED",
        "ipv4": [],
        "cpu_count": "",
        "memory": {},
        "disks": {"sda1": {}}
    })

    # Act
    status = await multipass_adapter.get_vm_status("test-vm")

    # Assert: falls back to sensible defaults without raising
    assert status.status.value == "stopped"
    assert status.resources.cpu == 1
    assert status.resources.memory == 1
    assert status.resources.storage == 10


@pytest.mark.asyncio
async def test_get_all_vms_resources_handles_empty_numeric_fields(multipass_adapter):
    # Arrange
    multipass_adapter._get_vm_info = AsyncMock(return_value={
        "state": "STOPPED",
        "ipv4": [],
        "cpu_count": "",
        "memory": {},
        "disks": {"sda1": {}}
    })

    # Act
    resources = await multipass_adapter.get_all_vms_resources()

    # Assert
    assert "test-vm" in resources
    assert resources["test-vm"].cpu == 1
    assert resources["test-vm"].memory == 1
    assert resources["test-vm"].storage == 10
