from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from provider.container import Container
from provider.main import app
from provider.monitoring.repo import MonitoringRepository
from provider.monitoring.services import MonitoringService
from provider.vm.domain import LeaseTerminationResult
from provider.vm.models import VMInfo, VMNotFoundError, VMResources, VMStatus
from provider.vm.service import VMService


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def mock_vm_service() -> VMService:
    return MagicMock(spec=VMService)


@pytest.fixture(autouse=True)
def override_container(mock_vm_service: VMService):
    class EmptyJobStore:
        async def active_recent_jobs(self):
            return []

    with app.container.vm_service.override(mock_vm_service):
        with app.container.job_store.override(EmptyJobStore()):
            yield


def test_create_vm_without_payment_is_rejected(
    client: TestClient, mock_vm_service: VMService
):
    # Arrange
    vm_info = VMInfo(
        id="test-vm",
        name="test-vm",
        status=VMStatus.RUNNING,
        resources=VMResources(cpu=2, memory=2, storage=20),
    )
    mock_vm_service.create_vm = AsyncMock(return_value=vm_info)
    request_data = {
        "name": "test-vm",
        "ssh_key": "ssh-rsa AAA...",
        "resources": {"cpu": 2, "memory": 2, "storage": 20},
    }

    # Act
    response = client.post("/api/v1/vms", json=request_data)

    # Assert
    assert response.status_code == 400
    assert "payment" in response.json()["detail"]


def test_list_vms_happy_path(client: TestClient, mock_vm_service: VMService):
    # Arrange
    vm_info = VMInfo(
        id="test-vm",
        name="test-vm",
        status=VMStatus.RUNNING,
        resources=VMResources(cpu=2, memory=2, storage=20),
    )
    mock_vm_service.list_vms = AsyncMock(return_value=[vm_info])

    # Act
    response = client.get("/api/v1/vms")

    # Assert
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["name"] == "test-vm"


def test_get_vm_status_happy_path(client: TestClient, mock_vm_service: VMService):
    # Arrange
    vm_info = VMInfo(
        id="test-vm",
        name="test-vm",
        status=VMStatus.RUNNING,
        resources=VMResources(cpu=2, memory=2, storage=20),
    )
    mock_vm_service.get_vm_status = AsyncMock(return_value=vm_info)

    # Act
    response = client.get("/api/v1/vms/test-vm")

    # Assert
    assert response.status_code == 200
    assert response.json()["name"] == "test-vm"


def test_monitoring_history_rejects_invalid_range(client: TestClient):
    response = client.get("/api/v1/monitoring/metrics/history?range=bogus")

    assert response.status_code == 422


def test_vm_metrics_history_rejects_invalid_range(client: TestClient):
    response = client.get("/api/v1/vms/test-vm/metrics/history?range=bogus")

    assert response.status_code == 422


def test_guest_sample_rejects_invalid_token(tmp_path):
    repo = MonitoringRepository(str(tmp_path / "monitoring.sqlite"))
    service = MonitoringService({}, repo, MagicMock(), MagicMock())
    app.container.monitoring_service.override(service)
    try:
        response = TestClient(app).post(
            "/api/v1/monitoring/guest/vm-a/samples",
            json={"token": "bad"},
        )
    finally:
        app.container.monitoring_service.reset_override()

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid guest metrics token"


def test_delete_vm_happy_path(client: TestClient, mock_vm_service: VMService):
    # Arrange
    mock_vm_service.delete_vm = AsyncMock()

    # Act
    response = client.delete("/api/v1/vms/test-vm")

    # Assert
    assert response.status_code == 200


def test_stop_vm_happy_path(client: TestClient, mock_vm_service: VMService):
    # Arrange
    vm_info = VMInfo(
        id="test-vm",
        name="test-vm",
        status=VMStatus.STOPPED,
        resources=VMResources(cpu=2, memory=2, storage=20),
    )
    mock_vm_service.stop_vm = AsyncMock(return_value=vm_info)

    # Act
    response = client.post("/api/v1/vms/test-vm/stop")

    # Assert
    assert response.status_code == 200
    assert response.json()["status"] == "stopped"


def test_stop_vm_not_found(client: TestClient, mock_vm_service: VMService):
    # Arrange
    mock_vm_service.stop_vm = AsyncMock(side_effect=VMNotFoundError("VM not found"))

    # Act
    response = client.post("/api/v1/vms/test-vm/stop")

    # Assert
    assert response.status_code == 404
    assert response.json()["detail"] == "VM not found"


def test_create_vm_invalid_data(client: TestClient):
    # Arrange
    request_data = {
        "name": "test-vm",
        # "ssh_key" is missing
        "resources": {"cpu": 2, "memory": 2, "storage": 20},
    }

    # Act
    response = client.post("/api/v1/vms", json=request_data)

    # Assert
    assert response.status_code == 422  # Unprocessable Entity


def test_get_vm_status_not_found(client: TestClient, mock_vm_service: VMService):
    # Arrange
    mock_vm_service.get_vm_status = AsyncMock(
        side_effect=VMNotFoundError("VM not found")
    )

    # Act
    response = client.get("/api/v1/vms/non-existent-vm")

    # Assert
    assert response.status_code == 404
    assert response.json()["detail"] == "VM not found"


def test_delete_vm_not_found(client: TestClient, mock_vm_service: VMService):
    # Arrange
    mock_vm_service.delete_vm = AsyncMock(side_effect=VMNotFoundError("VM not found"))

    # Act
    response = client.delete("/api/v1/vms/non-existent-vm")

    # Assert
    assert response.status_code == 404
    assert response.json()["detail"] == "VM not found"


def test_create_vm_service_exception(client: TestClient, mock_vm_service: VMService):
    # Arrange
    mock_vm_service.create_vm = AsyncMock(
        side_effect=Exception("Internal Server Error")
    )
    request_data = {
        "name": "test-vm",
        "ssh_key": "ssh-rsa AAA...",
        "resources": {"cpu": 2, "memory": 2, "storage": 20},
    }

    # Act
    response = client.post("/api/v1/vms", json=request_data)

    # Assert
    assert response.status_code == 400
    assert "payment" in response.json()["detail"]


def test_get_vm_status_service_exception(
    client: TestClient, mock_vm_service: VMService
):
    # Arrange
    mock_vm_service.get_vm_status = AsyncMock(
        side_effect=Exception("Internal Server Error")
    )

    # Act
    response = client.get("/api/v1/vms/test-vm")

    # Assert
    assert response.status_code == 502
    assert "failed to get VM status" in response.json()["detail"]


def test_delete_vm_service_exception(client: TestClient, mock_vm_service: VMService):
    # Arrange
    mock_vm_service.delete_vm = AsyncMock(
        side_effect=Exception("Internal Server Error")
    )

    # Act
    response = client.delete("/api/v1/vms/test-vm")

    # Assert
    assert response.status_code == 502
    assert "failed to delete VM" in response.json()["detail"]


def test_list_vms_service_exception(client: TestClient, mock_vm_service: VMService):
    # Arrange
    mock_vm_service.list_vms = AsyncMock(side_effect=Exception("Internal Server Error"))

    # Act
    response = client.get("/api/v1/vms")

    # Assert
    assert response.status_code == 502
    assert "failed to list VMs" in response.json()["detail"]


def test_list_vms_multipass_error(client: TestClient, mock_vm_service: VMService):
    # Arrange
    from provider.vm.multipass_adapter import MultipassError

    mock_vm_service.list_vms = AsyncMock(side_effect=MultipassError("mp failed"))

    # Act
    response = client.get("/api/v1/vms")

    # Assert
    assert response.status_code == 502


def test_get_vm_status_multipass_error(client: TestClient, mock_vm_service: VMService):
    # Arrange
    from provider.vm.multipass_adapter import MultipassError

    mock_vm_service.get_vm_status = AsyncMock(side_effect=MultipassError("mp failed"))

    # Act
    response = client.get("/api/v1/vms/test-vm")

    # Assert
    assert response.status_code == 502


def test_stop_vm_multipass_error(client: TestClient, mock_vm_service: VMService):
    # Arrange
    from provider.vm.multipass_adapter import MultipassError

    mock_vm_service.stop_vm = AsyncMock(side_effect=MultipassError("mp failed"))

    # Act
    response = client.post("/api/v1/vms/test-vm/stop")

    # Assert
    assert response.status_code == 502


def test_delete_vm_multipass_error(client: TestClient, mock_vm_service: VMService):
    # Arrange
    from provider.vm.multipass_adapter import MultipassError

    mock_vm_service.delete_vm = AsyncMock(side_effect=MultipassError("mp failed"))

    # Act
    response = client.delete("/api/v1/vms/test-vm")

    # Assert
    assert response.status_code == 502


def test_delete_vm_surfaces_stream_remove_failure(
    client: TestClient, mock_vm_service: VMService
):
    # Arrange
    mock_vm_service.delete_vm = AsyncMock()
    # Inject a stream_map that raises on remove
    class BadMap:
        async def remove(self, *_):
            raise RuntimeError("remove failed")

    app.container.stream_map.override(BadMap())

    # Act
    response = client.delete("/api/v1/vms/test-vm")

    # Assert
    assert response.status_code == 502
    app.container.stream_map.reset_override()


def test_stop_vm_generic_exception(client: TestClient, mock_vm_service: VMService):
    # Arrange
    mock_vm_service.stop_vm = AsyncMock(side_effect=Exception("boom"))

    # Act
    response = client.post("/api/v1/vms/test-vm/stop")

    # Assert
    assert response.status_code == 502


def test_admin_terminate_lease_happy_path(client: TestClient):
    class TerminationService:
        async def terminate_lease_by_provider(self, vm_id):
            return LeaseTerminationResult(
                vm=VMInfo(
                    id=vm_id,
                    name=vm_id,
                    status=VMStatus.TERMINATED,
                    resources=VMResources(cpu=1, memory=1, storage=10),
                    lifecycle_stage="provider_terminated",
                    status_message="VM lease was terminated by provider",
                    progress=100,
                    transitioning=False,
                ),
                stream_id=42,
                payment_state="terminated",
                termination_reason="provider_terminated",
                terminated_by="provider",
                terminated_at="2026-05-14T12:00:00+00:00",
                settlement_tx_hash="0xtx",
                cleanup_state="completed",
            )

    old = dict(app.container.config())
    cfg = dict(old)
    cfg["PROVIDER_ADMIN_TOKEN"] = "secret"
    app.container.config.override(cfg)
    app.container.vm_application_service.override(TerminationService())
    try:
        response = client.post(
            "/api/v1/admin/vms/test-vm/terminate-lease",
            headers={"Authorization": "Bearer secret"},
        )
    finally:
        app.container.vm_application_service.reset_override()
        app.container.config.override(old)

    assert response.status_code == 200
    assert response.json()["vm"]["status"] == "terminated"
    assert response.json()["terminated_by"] == "provider"


@pytest.mark.parametrize(
    "payload",
    [
        {
            "name": "test-vm",
            "ssh_key": "ssh-rsa AAA...",
            "resources": {"cpu": -1, "memory": 2, "storage": 20},
        },
        {
            "name": "test-vm",
            "ssh_key": "ssh-rsa AAA...",
            "resources": {"cpu": 2, "memory": -1, "storage": 20},
        },
        {
            "name": "test-vm",
            "ssh_key": "ssh-rsa AAA...",
            "resources": {"cpu": 2, "memory": 2, "storage": -1},
        },
    ],
)
def test_create_vm_invalid_resources(client: TestClient, payload: dict):
    # Act
    response = client.post("/api/v1/vms", json=payload)

    # Assert
    assert response.status_code == 422  # Unprocessable Entity


def test_create_vm_invalid_ssh_key(client: TestClient):
    # Arrange
    request_data = {
        "name": "test-vm",
        "ssh_key": "invalid-ssh-key",
        "resources": {"cpu": 2, "memory": 2, "storage": 20},
    }

    # Act
    response = client.post("/api/v1/vms", json=request_data)

    # Assert
    assert response.status_code == 422  # Unprocessable Entity
