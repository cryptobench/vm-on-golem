from unittest.mock import AsyncMock, MagicMock, call

import pytest

from provider.config import Settings
from provider.discovery.resource_tracker import ResourceTracker
from provider.errors import ConflictError, ValidationError
from provider.vm.models import VMConfig, VMInfo, VMResources, VMStatus
from provider.vm.provider import VMProvider
from provider.vm.service import VMService


@pytest.fixture
def mock_resource_tracker():
    tracker = MagicMock(spec=ResourceTracker)
    tracker.allocate = AsyncMock(return_value=True)
    tracker.deallocate = AsyncMock()
    tracker.resize = AsyncMock(return_value=True)
    return tracker


@pytest.fixture
def mock_vm_provider():
    provider = MagicMock(spec=VMProvider)
    provider.create_vm = AsyncMock(
        return_value=VMInfo(
            id="test-vm",
            name="test-vm",
            status=VMStatus.RUNNING,
            resources=VMResources(cpu=2, memory=2, storage=20),
        )
    )
    provider.delete_vm = AsyncMock()
    provider.list_vms = AsyncMock(return_value=[])
    provider.get_vm_status = AsyncMock()
    provider.resize_vm = AsyncMock()
    provider.start_vm = AsyncMock()
    provider.stop_vm = AsyncMock()
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
        name_mapper=name_mapper,
    )


@pytest.mark.asyncio
async def test_create_vm_happy_path(
    vm_service, mock_resource_tracker, mock_vm_provider
):
    # Arrange
    config = VMConfig(
        name="test-vm",
        ssh_key="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQD...",
        resources=VMResources(cpu=2, memory=2, storage=20),
    )

    # Act
    vm_info = await vm_service.create_vm(config)

    # Assert
    mock_resource_tracker.allocate.assert_awaited_once_with(
        config.resources, config.name
    )
    mock_vm_provider.create_vm.assert_awaited_once_with(config, None)
    assert vm_info.name == "test-vm"
    assert vm_info.status == VMStatus.RUNNING


@pytest.mark.asyncio
async def test_create_vm_allocation_fails(vm_service, mock_resource_tracker):
    # Arrange
    mock_resource_tracker.allocate.return_value = False
    config = VMConfig(
        name="test-vm",
        ssh_key="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQD...",
        resources=VMResources(cpu=2, memory=2, storage=20),
    )

    # Act & Assert
    with pytest.raises(
        ValueError, match="Insufficient resources available on provider"
    ):
        await vm_service.create_vm(config)


@pytest.mark.asyncio
async def test_create_vm_provider_fails_deallocates(
    vm_service, mock_resource_tracker, mock_vm_provider
):
    # Arrange
    mock_vm_provider.create_vm.side_effect = Exception("Provider Error")
    config = VMConfig(
        name="test-vm",
        ssh_key="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQD...",
        resources=VMResources(cpu=2, memory=2, storage=20),
    )

    # Act & Assert
    with pytest.raises(Exception, match="Provider Error"):
        await vm_service.create_vm(config)

    mock_resource_tracker.deallocate.assert_awaited_once_with(
        config.resources, config.name
    )


from provider.vm.models import VMNotFoundError


@pytest.mark.asyncio
async def test_delete_vm_happy_path(
    vm_service, mock_resource_tracker, mock_vm_provider
):
    # Arrange
    vm_info = VMInfo(
        id="test-vm",
        name="test-vm",
        status=VMStatus.RUNNING,
        resources=VMResources(cpu=2, memory=2, storage=20),
    )
    mock_vm_provider.get_vm_status.return_value = vm_info

    # Act
    await vm_service.delete_vm("test-vm")

    # Assert
    mock_vm_provider.delete_vm.assert_awaited_once_with("test-vm")
    mock_resource_tracker.deallocate.assert_awaited_once_with(
        vm_info.resources, "test-vm"
    )


@pytest.mark.asyncio
async def test_delete_vm_does_not_exist(vm_service, mock_vm_provider):
    # Arrange
    mock_vm_provider.get_vm_status.side_effect = VMNotFoundError("VM not found")

    with pytest.raises(VMNotFoundError):
        await vm_service.delete_vm("test-vm")

    mock_vm_provider.delete_vm.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_vm_no_mapping_raises(vm_service, mock_vm_provider):
    vm_service.name_mapper.get_multipass_name = AsyncMock(return_value=None)
    with pytest.raises(VMNotFoundError):
        await vm_service.delete_vm("ghost")
    mock_vm_provider.get_vm_status.assert_not_awaited()
    mock_vm_provider.delete_vm.assert_not_awaited()


@pytest.mark.asyncio
async def test_resize_vm_rejects_unsupported_state(vm_service, mock_vm_provider):
    mock_vm_provider.get_vm_status.return_value = VMInfo(
        id="test-vm",
        name="test-vm",
        status=VMStatus.SUSPENDED,
        resources=VMResources(cpu=1, memory=1, storage=10),
    )

    with pytest.raises(ConflictError, match="running or stopped"):
        await vm_service.resize_vm("test-vm", VMResources(cpu=2, memory=2, storage=20))

    mock_vm_provider.resize_vm.assert_not_called()


@pytest.mark.asyncio
async def test_resize_vm_updates_tracker_and_provider(
    vm_service, mock_resource_tracker, mock_vm_provider
):
    current = VMInfo(
        id="test-vm",
        name="test-vm",
        status=VMStatus.STOPPED,
        resources=VMResources(cpu=1, memory=1, storage=10),
    )
    resized = VMInfo(
        id="test-vm",
        name="test-vm",
        status=VMStatus.STOPPED,
        resources=VMResources(cpu=2, memory=4, storage=20),
    )
    mock_vm_provider.get_vm_status.return_value = current
    mock_vm_provider.resize_vm = AsyncMock(return_value=resized)

    result = await vm_service.resize_vm(
        "test-vm", VMResources(cpu=2, memory=4, storage=20)
    )

    assert result is resized
    mock_resource_tracker.resize.assert_awaited_once_with(
        "test-vm", VMResources(cpu=2, memory=4, storage=20)
    )
    mock_vm_provider.resize_vm.assert_awaited_once_with(
        "test-vm", VMResources(cpu=2, memory=4, storage=20)
    )
    mock_vm_provider.stop_vm.assert_not_awaited()
    mock_vm_provider.start_vm.assert_not_awaited()


@pytest.mark.asyncio
async def test_resize_running_vm_stops_resizes_and_restarts(
    vm_service, mock_resource_tracker, mock_vm_provider
):
    current = VMInfo(
        id="test-vm",
        name="test-vm",
        status=VMStatus.RUNNING,
        resources=VMResources(cpu=1, memory=1, storage=10),
    )
    resized = VMInfo(
        id="test-vm",
        name="test-vm",
        status=VMStatus.STOPPED,
        resources=VMResources(cpu=3, memory=9, storage=20),
    )
    restarted = resized.model_copy(update={"status": VMStatus.RUNNING})
    mock_vm_provider.get_vm_status.return_value = current
    mock_vm_provider.stop_vm.return_value = current.model_copy(
        update={"status": VMStatus.STOPPED}
    )
    mock_vm_provider.resize_vm.return_value = resized
    mock_vm_provider.start_vm.return_value = restarted

    result = await vm_service.resize_vm(
        "test-vm", VMResources(cpu=3, memory=9, storage=20)
    )

    assert result is restarted
    mock_vm_provider.stop_vm.assert_awaited_once_with("test-vm")
    mock_resource_tracker.resize.assert_awaited_once_with(
        "test-vm", VMResources(cpu=3, memory=9, storage=20)
    )
    mock_vm_provider.resize_vm.assert_awaited_once_with(
        "test-vm", VMResources(cpu=3, memory=9, storage=20)
    )
    mock_vm_provider.start_vm.assert_awaited_once_with("test-vm")


@pytest.mark.asyncio
async def test_resize_vm_rejects_storage_shrink(vm_service, mock_vm_provider):
    mock_vm_provider.get_vm_status.return_value = VMInfo(
        id="test-vm",
        name="test-vm",
        status=VMStatus.STOPPED,
        resources=VMResources(cpu=2, memory=2, storage=20),
    )

    with pytest.raises(ValidationError, match="storage can only be increased"):
        await vm_service.resize_vm("test-vm", VMResources(cpu=2, memory=2, storage=10))

    mock_vm_provider.resize_vm.assert_not_called()


@pytest.mark.asyncio
async def test_resize_vm_insufficient_capacity_fails_before_provider_resize(
    vm_service, mock_resource_tracker, mock_vm_provider
):
    mock_vm_provider.get_vm_status.return_value = VMInfo(
        id="test-vm",
        name="test-vm",
        status=VMStatus.STOPPED,
        resources=VMResources(cpu=1, memory=1, storage=10),
    )
    mock_resource_tracker.resize.return_value = False

    with pytest.raises(ValueError, match="Insufficient resources"):
        await vm_service.resize_vm("test-vm", VMResources(cpu=4, memory=8, storage=40))

    mock_vm_provider.resize_vm.assert_not_called()


@pytest.mark.asyncio
async def test_resize_vm_provider_failure_rolls_back_allocation(
    vm_service, mock_resource_tracker, mock_vm_provider
):
    current = VMInfo(
        id="test-vm",
        name="test-vm",
        status=VMStatus.STOPPED,
        resources=VMResources(cpu=1, memory=1, storage=10),
    )
    target = VMResources(cpu=3, memory=9, storage=20)
    mock_vm_provider.get_vm_status.return_value = current
    mock_vm_provider.resize_vm.side_effect = RuntimeError("multipass failed")

    with pytest.raises(RuntimeError, match="multipass failed"):
        await vm_service.resize_vm("test-vm", target)

    assert mock_resource_tracker.resize.await_args_list == [
        call("test-vm", target),
        call("test-vm", current.resources),
    ]


@pytest.mark.asyncio
async def test_clone_vm_allocates_and_maps_destination(
    vm_service, mock_resource_tracker, mock_vm_provider
):
    source = VMInfo(
        id="source",
        name="source",
        status=VMStatus.STOPPED,
        resources=VMResources(cpu=1, memory=1, storage=10),
    )
    clone = VMInfo(
        id="clone",
        name="clone",
        status=VMStatus.STOPPED,
        resources=source.resources,
    )
    vm_service.name_mapper.get_multipass_name = AsyncMock(
        side_effect=[None, "source-mp"]
    )
    mock_vm_provider.get_vm_status.return_value = source
    mock_vm_provider.clone_vm = AsyncMock(return_value=clone)

    result = await vm_service.clone_vm("source", "clone")

    assert result is clone
    mock_resource_tracker.allocate.assert_awaited_once_with(source.resources, "clone")
    vm_service.name_mapper.add_mapping.assert_awaited_once()
    mock_vm_provider.clone_vm.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_vm_blockchain_try_except_is_noop(vm_service, mock_vm_provider):
    # Exercise the optional blockchain_client try/except path by raising on truthiness
    class BadBC:
        def __bool__(self):
            raise RuntimeError("bc boom")

    vm_service.blockchain_client = BadBC()
    vm_info = VMInfo(
        id="x",
        name="x",
        status=VMStatus.RUNNING,
        resources=VMResources(cpu=1, memory=1, storage=10),
    )
    mock_vm_provider.get_vm_status.return_value = vm_info
    await vm_service.delete_vm("x")
    mock_vm_provider.delete_vm.assert_awaited()


@pytest.mark.asyncio
async def test_stop_vm_blockchain_try_except_is_noop(vm_service, mock_vm_provider):
    class BadBC:
        def __bool__(self):
            raise RuntimeError("bc boom")

    vm_service.blockchain_client = BadBC()
    vm_service.name_mapper.get_multipass_name = AsyncMock(return_value="m-x")
    vm_info = VMInfo(
        id="x",
        name="x",
        status=VMStatus.STOPPED,
        resources=VMResources(cpu=1, memory=1, storage=10),
    )
    mock_vm_provider.stop_vm = AsyncMock(return_value=vm_info)
    out = await vm_service.stop_vm("x")
    assert out is vm_info


@pytest.mark.asyncio
async def test_delete_vm_blockchain_truthy_noop(vm_service, mock_vm_provider):
    # Truthy blockchain client should go through the no-op pass branch
    vm_service.blockchain_client = object()
    vm_info = VMInfo(
        id="y",
        name="y",
        status=VMStatus.RUNNING,
        resources=VMResources(cpu=1, memory=1, storage=10),
    )
    mock_vm_provider.get_vm_status.return_value = vm_info
    await vm_service.delete_vm("y")
    mock_vm_provider.delete_vm.assert_awaited()


@pytest.mark.asyncio
async def test_stop_vm_blockchain_truthy_noop(vm_service, mock_vm_provider):
    vm_service.blockchain_client = object()
    vm_service.name_mapper.get_multipass_name = AsyncMock(return_value="m-y")
    vm_info = VMInfo(
        id="y",
        name="y",
        status=VMStatus.STOPPED,
        resources=VMResources(cpu=1, memory=1, storage=10),
    )
    mock_vm_provider.stop_vm = AsyncMock(return_value=vm_info)
    out = await vm_service.stop_vm("y")
    assert out is vm_info


@pytest.mark.asyncio
async def test_get_all_vms_resources(vm_service, mock_vm_provider):
    mock_vm_provider.get_all_vms_resources = AsyncMock(
        return_value={"id": VMResources(cpu=1, memory=1, storage=10)}
    )
    res = await vm_service.get_all_vms_resources()
    assert "id" in res and res["id"].cpu == 1


@pytest.mark.asyncio
async def test_get_vm_status_no_mapping_raises(vm_service, mock_vm_provider):
    vm_service.name_mapper.get_multipass_name = AsyncMock(return_value=None)
    with pytest.raises(VMNotFoundError):
        await vm_service.get_vm_status("ghost")


@pytest.mark.asyncio
async def test_delete_vm_provider_fails(vm_service, mock_vm_provider):
    # Arrange
    vm_info = VMInfo(
        id="test-vm",
        name="test-vm",
        status=VMStatus.RUNNING,
        resources=VMResources(cpu=2, memory=2, storage=20),
    )
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
    vm_info = VMInfo(
        id="test-vm",
        name="test-vm",
        status=VMStatus.RUNNING,
        resources=VMResources(cpu=2, memory=2, storage=20),
    )
    mock_vm_provider.list_vms.return_value = [vm_info]

    # Act
    vms = await vm_service.list_vms()

    # Assert
    assert vms == [vm_info]


@pytest.mark.asyncio
async def test_get_vm_status_happy_path(vm_service, mock_vm_provider):
    # Arrange
    vm_info = VMInfo(
        id="test-vm",
        name="test-vm",
        status=VMStatus.RUNNING,
        resources=VMResources(cpu=2, memory=2, storage=20),
    )
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
async def test_stop_vm_happy_path(vm_service, mock_vm_provider):
    # Arrange
    vm_service.name_mapper.get_multipass_name = AsyncMock(
        return_value="multipass-test-vm"
    )
    vm_info = VMInfo(
        id="test-vm",
        name="test-vm",
        status=VMStatus.STOPPED,
        resources=VMResources(cpu=2, memory=2, storage=20),
    )
    mock_vm_provider.stop_vm = AsyncMock(return_value=vm_info)

    # Act
    result = await vm_service.stop_vm("test-vm")

    # Assert
    vm_service.name_mapper.get_multipass_name.assert_awaited_once_with("test-vm")
    mock_vm_provider.stop_vm.assert_awaited_once_with("multipass-test-vm")
    assert result == vm_info


@pytest.mark.asyncio
async def test_stop_vm_not_found(vm_service, mock_vm_provider):
    # Arrange
    vm_service.name_mapper.get_multipass_name = AsyncMock(return_value=None)

    # Act & Assert
    with pytest.raises(VMNotFoundError):
        await vm_service.stop_vm("test-vm")
    mock_vm_provider.stop_vm.assert_not_awaited()


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
