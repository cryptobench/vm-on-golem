from provider.vm.lifecycle import creation_lifecycle, lifecycle_for_status
from provider.vm.models import VMInfo, VMResources, VMStatus


def test_vm_info_populates_lifecycle_fields_for_all_statuses():
    for status in VMStatus:
        info = VMInfo(
            id=f"vm-{status.value}",
            name=f"vm-{status.value}",
            status=status,
            resources=VMResources(cpu=1, memory=1, storage=10),
        )

        assert info.lifecycle_stage
        assert info.status_message
        assert 0 <= info.progress <= 100
        assert info.next_poll_seconds >= 1


def test_transitioning_statuses_use_fast_polling():
    state = lifecycle_for_status(VMStatus.STARTING)

    assert state.transitioning is True
    assert state.next_poll_seconds == 2
    assert state.status_message == "Starting VM"


def test_creation_lifecycle_preserves_stage_message_and_progress():
    state = creation_lifecycle(
        "configuring_access",
        "Configuring SSH access",
        90,
    )

    assert state.status == VMStatus.CREATING
    assert state.lifecycle_stage == "configuring_access"
    assert state.status_message == "Configuring SSH access"
    assert state.progress == 90
