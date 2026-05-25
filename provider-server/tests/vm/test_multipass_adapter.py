import subprocess
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from provider.monitoring.domain import GuestAgentState
from provider.vm.models import VMConfig, VMInfo, VMNotFoundError, VMResources, VMStatus
from provider.vm.multipass_adapter import MultipassAdapter, MultipassError


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.MULTIPASS_BINARY_PATH = "/usr/local/bin/multipass"
    settings.MULTIPASS_LAUNCH_INIT_TIMEOUT_SECONDS = 1
    settings.LAUNCH_TIMEOUT_SECONDS = 300
    settings.CREATE_VM_MAX_RETRIES = 2
    settings.CREATE_VM_RETRY_DELAY_SECONDS = 0.01
    settings.VM_AGENT_STATE_STALE_SECONDS = 90
    return settings


@pytest.fixture
def multipass_adapter(mock_settings):
    with patch("provider.vm.multipass_adapter.settings", mock_settings):
        proxy_manager = AsyncMock()
        proxy_manager.add_vm = AsyncMock(return_value=True)
        proxy_manager.remove_vm = AsyncMock()
        proxy_manager.get_port = MagicMock(return_value=2222)

        name_mapper = AsyncMock()
        name_mapper.add_mapping = AsyncMock()
        name_mapper.get_multipass_name = AsyncMock(return_value="multipass-vm-name")
        name_mapper.get_requestor_name = AsyncMock(return_value="test-vm")
        name_mapper.remove_mapping = AsyncMock()
        name_mapper.list_mappings = MagicMock(
            return_value={"test-vm": "multipass-vm-name"}
        )

        monitoring_repo = MagicMock()
        monitoring_repo.get_guest_agent_state = MagicMock(
            return_value=guest_state("test-vm")
        )
        resource_tracker = MagicMock()
        resource_tracker.get_allocated_resources_for = MagicMock(
            return_value=VMResources(cpu=2, memory=2, storage=20)
        )

        adapter = MultipassAdapter(
            proxy_manager,
            name_mapper,
            monitoring_repo=monitoring_repo,
            resource_tracker=resource_tracker,
        )
        adapter._run_multipass = AsyncMock()
        return adapter


def guest_state(
    vm_id="test-vm",
    *,
    source_ip="192.168.2.17",
    agent_ready=True,
    sshd_ready=True,
    hardening_applied=True,
    last_seen_at=None,
):
    return GuestAgentState(
        vm_id=vm_id,
        source_ip=source_ip,
        agent_ready=agent_ready,
        sshd_ready=sshd_ready,
        hardening_applied=hardening_applied,
        agent_version="test",
        last_seen_at=last_seen_at or datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_verify_installation_success(multipass_adapter):
    # Arrange
    mock_process = MagicMock()
    mock_process.stdout = "multipass 1.13.1+mac"
    multipass_adapter._run_multipass.return_value = mock_process

    # Act & Assert
    try:
        with patch.object(
            multipass_adapter, "_check_host_virtualization_compatibility"
        ):
            await multipass_adapter.initialize()
    except MultipassError:
        pytest.fail("MultipassError was raised unexpectedly")


@pytest.mark.asyncio
async def test_initialize_restores_missing_proxy_for_running_vm(multipass_adapter):
    mock_process = MagicMock()
    mock_process.stdout = "multipass 1.16.1+mac"
    multipass_adapter._run_multipass.return_value = mock_process
    multipass_adapter.proxy_manager.get_port = MagicMock(return_value=None)
    multipass_adapter.proxy_manager.add_vm = AsyncMock(return_value=True)
    multipass_adapter._get_vm_info = AsyncMock(
        return_value={
            "state": "RUNNING",
            "ipv4": ["192.168.2.4"],
            "cpu_count": "1",
            "memory": {"total": 2147483648},
            "disks": {"sda1": {"total": 21474836480}},
        }
    )

    with patch.object(multipass_adapter, "_check_host_virtualization_compatibility"):
        await multipass_adapter.initialize()

    multipass_adapter.proxy_manager.add_vm.assert_awaited_once_with(
        "multipass-vm-name", "192.168.2.4"
    )


@pytest.mark.asyncio
async def test_initialize_does_not_report_or_create_proxy_for_stopped_vm(
    multipass_adapter,
):
    mock_process = MagicMock()
    mock_process.stdout = "multipass 1.16.1+mac"
    multipass_adapter._run_multipass.return_value = mock_process
    multipass_adapter.proxy_manager.get_port = MagicMock(return_value=None)
    multipass_adapter.proxy_manager.add_vm = AsyncMock(return_value=True)
    multipass_adapter.monitoring_repo.get_guest_agent_state = MagicMock(
        return_value=None
    )
    multipass_adapter._get_vm_info = AsyncMock(
        return_value={
            "state": "Stopped",
            "ipv4": [],
            "cpu_count": "1",
            "memory": {"total": 2147483648},
            "disks": {"sda1": {"total": 21474836480}},
        }
    )

    with patch.object(multipass_adapter, "_check_host_virtualization_compatibility"):
        await multipass_adapter.initialize()

    multipass_adapter.proxy_manager.add_vm.assert_not_awaited()


@pytest.mark.asyncio
async def test_initialize_restores_missing_proxy_from_guest_state_when_multipass_has_no_ip(
    multipass_adapter,
):
    mock_process = MagicMock()
    mock_process.stdout = "multipass 1.16.1+mac"
    multipass_adapter._run_multipass.return_value = mock_process
    multipass_adapter.proxy_manager.get_port = MagicMock(return_value=None)
    multipass_adapter.proxy_manager.add_vm = AsyncMock(return_value=True)
    multipass_adapter.monitoring_repo.get_guest_agent_state = MagicMock(
        return_value=guest_state("test-vm", source_ip="192.168.2.19")
    )
    multipass_adapter._get_vm_info = AsyncMock(
        return_value={
            "state": "Unknown",
            "ipv4": [],
            "cpu_count": "1",
            "memory": {"total": 2147483648},
            "disks": {"sda1": {"total": 21474836480}},
        }
    )

    with patch.object(multipass_adapter, "_check_host_virtualization_compatibility"):
        await multipass_adapter.initialize()

    multipass_adapter.proxy_manager.add_vm.assert_awaited_once_with(
        "multipass-vm-name", "192.168.2.19"
    )


@pytest.mark.asyncio
async def test_verify_installation_failure(multipass_adapter):
    # Arrange
    multipass_adapter._run_multipass.side_effect = MultipassError("Command failed")

    # Act & Assert
    with pytest.raises(MultipassError):
        await multipass_adapter.initialize()


@pytest.mark.asyncio
async def test_run_multipass_captures_launch_stderr(multipass_adapter):
    run_multipass = MultipassAdapter._run_multipass.__get__(
        multipass_adapter, MultipassAdapter
    )
    with patch("provider.vm.multipass_adapter.subprocess.run") as run:
        run.side_effect = subprocess.CalledProcessError(
            2,
            ["/usr/local/bin/multipass", "launch", "ubuntu:24.04"],
            stderr="launch failed: Remote 'ubuntu' is not found.",
        )

        with pytest.raises(MultipassError, match="Remote 'ubuntu' is not found"):
            await run_multipass(["launch", "ubuntu:24.04"])

    assert run.call_args.kwargs["capture_output"] is True


def test_rejects_known_broken_macos_qemu_driver(multipass_adapter, tmp_path):
    qemu = tmp_path / "qemu-system-aarch64"
    qemu.write_text("#!/bin/sh\necho 'QEMU emulator version 8.2.1'\n")
    qemu.chmod(0o755)
    multipass = tmp_path / "multipass"
    multipass.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = 'get' ]; then echo qemu; exit 0; fi\n"
        "if [ \"$1\" = 'version' ]; then echo 'multipass   1.16.2+mac'; exit 0; fi\n"
    )
    multipass.chmod(0o755)
    multipass_adapter.multipass_path = str(multipass)

    with patch(
        "provider.vm.multipass_requirements.platform.system", return_value="Darwin"
    ):
        with patch(
            "provider.vm.multipass_requirements.platform.machine", return_value="arm64"
        ):
            with patch(
                "provider.vm.multipass_requirements.platform.release",
                return_value="25.2.0",
            ):
                with pytest.raises(MultipassError, match="host-arm-cpu.sme"):
                    multipass_adapter._check_host_virtualization_compatibility()


def test_allows_multipass_1_16_1_macos_qemu_driver(multipass_adapter, tmp_path):
    qemu = tmp_path / "qemu-system-aarch64"
    qemu.write_text("#!/bin/sh\necho 'QEMU emulator version 8.2.1'\n")
    qemu.chmod(0o755)
    multipass = tmp_path / "multipass"
    multipass.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = 'get' ]; then echo qemu; exit 0; fi\n"
        "if [ \"$1\" = 'version' ]; then echo 'multipass   1.16.1+mac'; exit 0; fi\n"
    )
    multipass.chmod(0o755)
    multipass_adapter.multipass_path = str(multipass)

    with patch(
        "provider.vm.multipass_requirements.platform.system", return_value="Darwin"
    ):
        with patch(
            "provider.vm.multipass_requirements.platform.machine", return_value="arm64"
        ):
            with patch(
                "provider.vm.multipass_requirements.platform.release",
                return_value="25.2.0",
            ):
                multipass_adapter._check_host_virtualization_compatibility()


@pytest.mark.asyncio
async def test_create_vm_happy_path(multipass_adapter):
    # Arrange
    config = VMConfig(
        name="test-vm",
        image="22.04",
        ssh_key="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQD...",
        cloud_init_path="/path/to/cloud-init",
        resources=VMResources(cpu=2, memory=2, storage=20),
    )
    multipass_adapter._get_vm_info = AsyncMock()

    # Act
    vm = await multipass_adapter.create_vm(config)

    # Assert
    multipass_adapter._run_multipass.assert_called()
    launch_call_args = multipass_adapter._run_multipass.call_args[0][0]
    assert launch_call_args[0] == "launch"
    assert launch_call_args[1] == config.image
    assert launch_call_args[2] == "--name"
    assert launch_call_args[3].startswith("golem-")
    assert "--timeout" in launch_call_args
    assert launch_call_args[launch_call_args.index("--timeout") + 1] == "60"
    multipass_adapter.name_mapper.add_mapping.assert_awaited_once()
    multipass_adapter._get_vm_info.assert_not_called()
    assert vm.status == VMStatus.RUNNING
    assert vm.ip_address == "192.168.2.17"


@pytest.mark.asyncio
async def test_create_vm_normalizes_legacy_ubuntu_remote_for_launch(multipass_adapter):
    config = VMConfig(
        name="test-vm",
        image="ubuntu:24.04",
        ssh_key="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQD...",
        cloud_init_path="/path/to/cloud-init",
        resources=VMResources(cpu=2, memory=2, storage=20),
    )
    await multipass_adapter.create_vm(config)

    launch_call_args = multipass_adapter._run_multipass.call_args[0][0]
    assert launch_call_args[0] == "launch"
    assert launch_call_args[1] == "24.04"


@pytest.mark.asyncio
async def test_create_vm_with_preassigned_multipass_name_registers_mapping(
    multipass_adapter,
):
    config = VMConfig(
        name="test-vm",
        image="ubuntu:22.04",
        ssh_key="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQD...",
        cloud_init_path="/path/to/cloud-init",
        resources=VMResources(cpu=2, memory=2, storage=20),
        multipass_name="golem-stable",
    )
    multipass_adapter.name_mapper.get_requestor_name = AsyncMock(return_value=None)
    multipass_adapter.name_mapper.get_multipass_name = AsyncMock(
        return_value="golem-stable"
    )
    multipass_adapter._get_vm_info = AsyncMock()

    vm = await multipass_adapter.create_vm(config)

    multipass_adapter.name_mapper.add_mapping.assert_awaited_once_with(
        "test-vm", "golem-stable"
    )
    multipass_adapter.name_mapper.get_multipass_name.assert_awaited_with("test-vm")
    multipass_adapter._get_vm_info.assert_not_called()
    assert vm.id == "test-vm"


@pytest.mark.asyncio
async def test_create_vm_multipass_fails(multipass_adapter):
    # Arrange
    config = VMConfig(
        name="test-vm",
        image="ubuntu:22.04",
        ssh_key="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQD...",
        cloud_init_path="/path/to/cloud-init",
        resources=VMResources(cpu=2, memory=2, storage=20),
    )
    multipass_adapter._run_multipass.side_effect = MultipassError(
        "Multipass command failed"
    )
    multipass_adapter.proxy_manager.remove_vm = AsyncMock()

    # Act & Assert
    with pytest.raises(MultipassError):
        await multipass_adapter.create_vm(config)


@pytest.mark.asyncio
async def test_create_vm_detaches_from_multipass_guest_initialization_timeout(
    multipass_adapter,
):
    config = VMConfig(
        name="test-vm",
        image="ubuntu:22.04",
        ssh_key="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQD...",
        cloud_init_path="/path/to/cloud-init",
        resources=VMResources(cpu=2, memory=2, storage=20),
        multipass_name="golem-stable",
    )
    multipass_adapter.name_mapper.get_requestor_name = AsyncMock(return_value=None)
    multipass_adapter.name_mapper.get_multipass_name = AsyncMock(
        return_value="golem-stable"
    )
    multipass_adapter._run_multipass.side_effect = MultipassError(
        "launch failed: timed out waiting for initialization to complete"
    )
    multipass_adapter._get_vm_info = AsyncMock()

    vm = await multipass_adapter.create_vm(config)

    assert vm.id == "test-vm"
    assert vm.ssh_port == 2222
    multipass_adapter.proxy_manager.add_vm.assert_awaited_once_with(
        "golem-stable", "192.168.2.17"
    )
    multipass_adapter._get_vm_info.assert_not_called()


@pytest.mark.asyncio
async def test_delete_vm_happy_path(multipass_adapter):
    # Arrange
    multipass_adapter.name_mapper.get_requestor_name = AsyncMock(return_value="test-vm")

    # Act
    await multipass_adapter.delete_vm("test-vm")

    # Assert
    multipass_adapter._run_multipass.assert_called_once_with(
        ["delete", "test-vm", "--purge"], check=False
    )
    multipass_adapter.name_mapper.remove_mapping.assert_awaited_once_with("test-vm")


@pytest.mark.asyncio
async def test_delete_vm_does_not_exist(multipass_adapter):
    # Arrange
    multipass_adapter.name_mapper.get_requestor_name = AsyncMock(return_value=None)

    # Act
    await multipass_adapter.delete_vm("test-vm")

    # Assert
    multipass_adapter._run_multipass.assert_called_once_with(
        ["delete", "test-vm", "--purge"], check=False
    )
    multipass_adapter.name_mapper.remove_mapping.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_vm_status_happy_path(multipass_adapter):
    multipass_adapter._get_vm_info = AsyncMock()

    # Act
    status = await multipass_adapter.get_vm_status("test-vm")

    # Assert
    assert status.status.value == "running"
    assert status.lifecycle_stage == "ready"
    assert status.ip_address == "192.168.2.17"
    assert status.ssh_port == 2222
    assert status.resources.cpu == 2
    assert status.resources.memory == 2
    assert status.resources.storage == 20
    multipass_adapter._get_vm_info.assert_not_called()


@pytest.mark.asyncio
async def test_get_vm_status_vm_not_found(multipass_adapter):
    # Arrange
    multipass_adapter.name_mapper.get_requestor_name = AsyncMock(return_value=None)
    multipass_adapter.name_mapper.get_multipass_name = AsyncMock(return_value=None)

    # Act & Assert
    with pytest.raises(VMNotFoundError):
        await multipass_adapter.get_vm_status("non-existent-vm")


@pytest.mark.asyncio
async def test_create_vm_without_guest_metrics_fails(multipass_adapter):
    # Arrange
    config = VMConfig(
        name="test-vm",
        image="ubuntu:22.04",
        ssh_key="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQD...",
        cloud_init_path="/path/to/cloud-init",
        resources=VMResources(cpu=2, memory=2, storage=20),
    )
    multipass_adapter.monitoring_repo.get_guest_agent_state = MagicMock(
        return_value=None
    )
    multipass_adapter._get_vm_info = AsyncMock()

    # Act & Assert
    with pytest.raises(MultipassError):
        await multipass_adapter.create_vm(config)
    multipass_adapter.proxy_manager.add_vm.assert_not_awaited()
    multipass_adapter._get_vm_info.assert_not_called()


@pytest.mark.asyncio
async def test_delete_vm_multipass_fails(multipass_adapter):
    # Arrange
    multipass_adapter.name_mapper.get_requestor_name = AsyncMock(return_value="test-vm")
    multipass_adapter._run_multipass.side_effect = MultipassError(
        "Multipass command failed"
    )

    # Act & Assert
    with pytest.raises(MultipassError):
        await multipass_adapter.delete_vm("test-vm")


@pytest.mark.asyncio
async def test_get_vm_status_not_running(multipass_adapter):
    stale = guest_state(
        last_seen_at=datetime.now(timezone.utc) - timedelta(seconds=120)
    )
    multipass_adapter.monitoring_repo.get_guest_agent_state = MagicMock(
        return_value=stale
    )

    # Act
    status = await multipass_adapter.get_vm_status("test-vm")

    # Assert
    assert status.status == VMStatus.UNKNOWN
    assert status.lifecycle_stage == "agent_stale"
    assert status.status_message == "Guest agent heartbeat is stale"
    assert status.ip_address == "192.168.2.17"


@pytest.mark.asyncio
async def test_get_vm_status_partial_agent_readiness_is_running(
    multipass_adapter,
):
    multipass_adapter.monitoring_repo.get_guest_agent_state = MagicMock(
        return_value=guest_state(sshd_ready=False)
    )

    # Act
    status = await multipass_adapter.get_vm_status("test-vm")

    # Assert
    assert status.status == VMStatus.RUNNING
    assert status.lifecycle_stage == "ready"
    assert status.status_message == "VM is online"


@pytest.mark.asyncio
async def test_parse_vm_info_missing_fields(multipass_adapter):
    # Arrange
    mock_process = MagicMock()
    mock_process.stdout = (
        '{"info": {"test-vm": {"state": "RUNNING"}}}'  # Missing fields
    )
    multipass_adapter._run_multipass.return_value = mock_process

    # Act & Assert
    with pytest.raises(MultipassError):
        await multipass_adapter._get_vm_info("test-vm")


from pydantic import ValidationError


@pytest.mark.parametrize(
    "resources_data, expected_error",
    [
        (
            {"cpu": 0, "memory": 2, "storage": 20},
            "Input should be greater than or equal to 1",
        ),
        (
            {"cpu": 2, "memory": 0, "storage": 20},
            "Input should be greater than or equal to 1",
        ),
        (
            {"cpu": 2, "memory": 2, "storage": 9},
            "Input should be greater than or equal to 10",
        ),
    ],
)
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
async def test_list_vms_preserves_mapping_for_active_creation(multipass_adapter):
    multipass_adapter.get_vm_status = AsyncMock(
        side_effect=VMNotFoundError("VM test-vm not found")
    )
    multipass_adapter._creating_multipass_names.add("multipass-vm-name")

    vms = await multipass_adapter.list_vms()

    assert vms == []
    multipass_adapter.proxy_manager.remove_vm.assert_not_awaited()
    multipass_adapter.name_mapper.remove_mapping.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_vms_cleans_stale_mapping_when_not_creating(multipass_adapter):
    multipass_adapter.get_vm_status = AsyncMock(
        side_effect=VMNotFoundError("VM test-vm not found")
    )

    vms = await multipass_adapter.list_vms()

    assert vms == []
    multipass_adapter.proxy_manager.remove_vm.assert_awaited_once_with(
        "multipass-vm-name"
    )
    multipass_adapter.name_mapper.remove_mapping.assert_awaited_once_with("test-vm")


@pytest.mark.asyncio
async def test_get_all_vms_resources(multipass_adapter):
    # Arrange
    multipass_adapter._get_vm_info = AsyncMock(
        return_value={
            "state": "RUNNING",
            "ipv4": ["192.168.64.2"],
            "cpu_count": "2",
            "memory": {"total": 2147483648},
            "disks": {"sda1": {"total": 10737418240}},
        }
    )

    # Act
    resources = await multipass_adapter.get_all_vms_resources()

    # Assert
    assert "test-vm" in resources
    assert resources["test-vm"].cpu == 2
    assert resources["test-vm"].memory == 2
    assert resources["test-vm"].storage == 10


@pytest.mark.asyncio
async def test_get_all_vms_resources_preserves_mapping_for_active_creation(
    multipass_adapter,
):
    multipass_adapter._get_vm_info = AsyncMock(
        side_effect=VMNotFoundError("VM test-vm not found")
    )
    multipass_adapter._creating_multipass_names.add("multipass-vm-name")

    resources = await multipass_adapter.get_all_vms_resources()

    assert resources == {}
    multipass_adapter.proxy_manager.remove_vm.assert_not_awaited()
    multipass_adapter.name_mapper.remove_mapping.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_vm_clears_active_creation_after_success(multipass_adapter):
    config = VMConfig(
        name="test-vm",
        image="24.04",
        ssh_key="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQD...",
        cloud_init_path="/path/to/cloud-init",
        resources=VMResources(cpu=2, memory=2, storage=20),
        multipass_name="golem-stable",
    )
    multipass_adapter._get_vm_info = AsyncMock()

    await multipass_adapter.create_vm(config)

    assert "golem-stable" not in multipass_adapter._creating_multipass_names
    multipass_adapter._get_vm_info.assert_not_called()


@pytest.mark.asyncio
async def test_create_vm_clears_active_creation_after_failure(multipass_adapter):
    config = VMConfig(
        name="test-vm",
        image="24.04",
        ssh_key="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQD...",
        cloud_init_path="/path/to/cloud-init",
        resources=VMResources(cpu=2, memory=2, storage=20),
        multipass_name="golem-stable",
    )
    multipass_adapter._run_multipass.side_effect = MultipassError("launch failed")

    with pytest.raises(MultipassError):
        await multipass_adapter.create_vm(config)

    assert "golem-stable" not in multipass_adapter._creating_multipass_names


@pytest.mark.asyncio
async def test_get_vm_status_uses_allocated_resources(multipass_adapter):
    multipass_adapter._get_vm_info = AsyncMock(
        side_effect=AssertionError("status must not query multipass info")
    )

    status = await multipass_adapter.get_vm_status("test-vm")

    assert status.status == VMStatus.RUNNING
    assert status.resources == VMResources(cpu=2, memory=2, storage=20)
    multipass_adapter._get_vm_info.assert_not_called()


@pytest.mark.asyncio
async def test_get_all_vms_resources_handles_empty_numeric_fields(multipass_adapter):
    # Arrange
    multipass_adapter._get_vm_info = AsyncMock(
        return_value={
            "state": "STOPPED",
            "ipv4": [],
            "cpu_count": "",
            "memory": {},
            "disks": {"sda1": {}},
        }
    )

    # Act
    resources = await multipass_adapter.get_all_vms_resources()

    # Assert
    assert "test-vm" in resources
    assert resources["test-vm"].cpu == 1
    assert resources["test-vm"].memory == 1
    assert resources["test-vm"].storage == 10
