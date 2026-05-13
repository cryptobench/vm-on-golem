import pytest

from provider.discovery.resource_tracker import ResourceTracker
from provider.vm.models import VMResources


@pytest.mark.asyncio
async def test_resize_updates_available_resources_and_notifies_callbacks():
    tracker = ResourceTracker()
    tracker.total_resources = {"cpu": 8, "memory": 16, "storage": 100}
    tracker.allocated_resources = {"cpu": 1, "memory": 2, "storage": 10}
    tracker._allocated_vms = {"vm-1": VMResources(cpu=1, memory=2, storage=10)}
    notifications = []

    async def on_update():
        notifications.append(tracker.get_available_resources())

    tracker.on_update(on_update)

    resized = await tracker.resize("vm-1", VMResources(cpu=3, memory=9, storage=25))

    assert resized is True
    assert tracker.allocated_resources == {"cpu": 3, "memory": 9, "storage": 25}
    assert tracker.get_available_resources() == {
        "cpu": 5,
        "memory": 7,
        "storage": 75,
    }
    assert notifications == [{"cpu": 5, "memory": 7, "storage": 75}]
