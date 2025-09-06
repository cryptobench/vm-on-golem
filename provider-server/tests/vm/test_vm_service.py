import pytest
from unittest.mock import MagicMock, AsyncMock

from provider.vm.service import VMService
from provider.vm.models import VMConfig, VMResources, VMInfo, VMStatus
from provider.discovery.resource_tracker import ResourceTracker
from provider.vm.provider import VMProvider
from provider.config import Settings

@pytest.fixture
def mock_resource_tracker():
    tracker = MagicMock(spec=ResourceTracker)
    tracker.allocate = AsyncMock(return_value=True)
    tracker.deallocate = AsyncMock()
    return tracker

@pytest.fixture
def mock_vm_provider():
    provider = MagicMock(spec=VMProvider)
    provider.create_vm = AsyncMock(return_value=VMInfo(id="test-vm", name="test-vm", status=VMStatus.RUNNING, resources=VMResources(cpu=2, memory=2, storage=20)))
    provider.delete_vm = AsyncMock()
    provider.list_vms = AsyncMock(return_value=[])
    provider.get_vm_status = AsyncMock()
    return provider

@pytest.fixture
def mock_settings():
    settings = MagicMock(spec=Settings)
    settings.MIN_CPU_CORES = 1
    settings.MIN_MEMORY_GB = 1
    settings.MIN_STORAGE_GB = 10
    settings.DEFAULT_VM_IMAGE = "ubuntu:22.04"
    return settings

@pytest.fixture
def vm_service(mock_resource_tracker, mock_vm_provider, mock_settings):
    name_mapper = MagicMock()
    name_mapper.add_mapping = AsyncMock()
    name_mapper.get_multipass_name = AsyncMock(return_value="test-vm")
    name_mapper.remove_mapping = AsyncMock()
    return VMService(
        resource_tracker=mock_resource_tracker,
        provider=mock_vm_provider,
        name_mapper=name_mapper
    )

@pytest.mark.asyncio
async def test_create_vm_happy_path(vm_service, mock_resource_tracker, mock_vm_provider):
    # Arrange
    config = VMConfig(
        name="test-vm",
        ssh_key="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQD...",
        resources=VMResources(cpu=2, memory=2, storage=20)
    )

    # Act
    vm_info = await vm_service.create_vm(config)

    # Assert
    mock_resource_tracker.allocate.assert_awaited_once_with(config.resources, config.name)
    mock_vm_provider.create_vm.assert_awaited_once_with(config)
    assert vm_info.name == "test-vm"
    assert vm_info.status == VMStatus.RUNNING


@pytest.mark.asyncio
async def test_create_vm_allocation_fails(vm_service, mock_resource_tracker):
    # Arrange
    mock_resource_tracker.allocate.return_value = False
    config = VMConfig(
        name="test-vm",
        ssh_key="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQD...",
        resources=VMResources(cpu=2, memory=2, storage=20)
    )

    # Act & Assert
    with pytest.raises(ValueError, match="Insufficient resources available on provider"):
        await vm_service.create_vm(config)

@pytest.mark.asyncio
async def test_create_vm_provider_fails_deallocates(vm_service, mock_resource_tracker, mock_vm_provider):
    # Arrange
    mock_vm_provider.create_vm.side_effect = Exception("Provider Error")
    config = VMConfig(
        name="test-vm",
        ssh_key="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQD...",
        resources=VMResources(cpu=2, memory=2, storage=20)
    )

    # Act & Assert
    with pytest.raises(Exception, match="Provider Error"):
        await vm_service.create_vm(config)
    
    mock_resource_tracker.deallocate.assert_awaited_once_with(config.resources, config.name)

from provider.vm.models import VMNotFoundError

@pytest.mark.asyncio
async def test_delete_vm_happy_path(vm_service, mock_resource_tracker, mock_vm_provider):
    # Arrange
    vm_info = VMInfo(id="test-vm", name="test-vm", status=VMStatus.RUNNING, resources=VMResources(cpu=2, memory=2, storage=20))
    mock_vm_provider.get_vm_status.return_value = vm_info

    # Act
    await vm_service.delete_vm("test-vm")

    # Assert
    mock_vm_provider.delete_vm.assert_awaited_once_with("test-vm")
    mock_resource_tracker.deallocate.assert_awaited_once_with(vm_info.resources, "test-vm")

@pytest.mark.asyncio
async def test_delete_vm_does_not_exist(vm_service, mock_vm_provider):
    # Arrange
    mock_vm_provider.get_vm_status.side_effect = VMNotFoundError("VM not found")

    # Act &amp; Assert
    with pytest.raises(VMNotFoundError):
        await vm_service.delete_vm("test-vm")

@pytest.mark.asyncio
async def test_delete_vm_provider_fails(vm_service, mock_vm_provider):
    # Arrange
    vm_info = VMInfo(id="test-vm", name="test-vm", status=VMStatus.RUNNING, resources=VMResources(cpu=2, memory=2, storage=20))
    mock_vm_provider.get_vm_status.return_value = vm_info
    mock_vm_provider.delete_vm.side_effect = Exception("Provider Error")

    # Act &amp; Assert
    with pytest.raises(Exception, match="Provider Error"):
        await vm_service.delete_vm("test-vm")

@pytest.mark.asyncio
async def test_list_vms_no_vms(vm_service, mock_vm_provider):
    # Arrange
    mock_vm_provider.list_vms.return_value = []

    # Act
    vms = await vm_service.list_vms()

    # Assert
    assert vms == []

@pytest.mark.asyncio
async def test_list_vms_with_vms(vm_service, mock_vm_provider):
    # Arrange
    vm_info = VMInfo(id="test-vm", name="test-vm", status=VMStatus.RUNNING, resources=VMResources(cpu=2, memory=2, storage=20))
    mock_vm_provider.list_vms.return_value = [vm_info]

    # Act
    vms = await vm_service.list_vms()

    # Assert
    assert vms == [vm_info]

@pytest.mark.asyncio
async def test_get_vm_status_happy_path(vm_service, mock_vm_provider):
    # Arrange
    vm_info = VMInfo(id="test-vm", name="test-vm", status=VMStatus.RUNNING, resources=VMResources(cpu=2, memory=2, storage=20))
    mock_vm_provider.get_vm_status.return_value = vm_info

    # Act
    status = await vm_service.get_vm_status("test-vm")

    # Assert
    assert status == vm_info

@pytest.mark.asyncio
async def test_get_vm_status_does_not_exist(vm_service, mock_vm_provider):
    # Arrange
    mock_vm_provider.get_vm_status.side_effect = VMNotFoundError("VM not found")

    # Act &amp; Assert
    with pytest.raises(VMNotFoundError):
        await vm_service.get_vm_status("test-vm")

@pytest.mark.asyncio
async def test_initialize(vm_service, mock_vm_provider):
    # Act
    await vm_service.initialize()

    # Assert
    mock_vm_provider.initialize.assert_awaited_once()

@pytest.mark.asyncio
async def test_shutdown(vm_service, mock_vm_provider):
    # Act
    await vm_service.shutdown()

    # Assert
    mock_vm_provider.cleanup.assert_awaited_once()
