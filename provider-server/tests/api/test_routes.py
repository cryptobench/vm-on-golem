import pytest
from unittest.mock import MagicMock, AsyncMock
from fastapi.testclient import TestClient
from provider.main import app
from provider.container import Container
from provider.vm.service import VMService
from provider.vm.models import VMInfo, VMStatus, VMResources

@pytest.fixture
def client() -> TestClient:
    return TestClient(app)

@pytest.fixture
def mock_vm_service() -> VMService:
    return MagicMock(spec=VMService)

@pytest.fixture(autouse=True)
def override_container(mock_vm_service: VMService):
    with app.container.vm_service.override(mock_vm_service):
        yield

def test_create_vm_happy_path(client: TestClient, mock_vm_service: VMService):
    # Arrange
    vm_info = VMInfo(id="test-vm", name="test-vm", status=VMStatus.RUNNING, resources=VMResources(cpu=2, memory=2, storage=20))
    mock_vm_service.create_vm = AsyncMock(return_value=vm_info)
    request_data = {
        "name": "test-vm",
        "ssh_key": "ssh-rsa AAA...",
        "resources": {"cpu": 2, "memory": 2, "storage": 20}
    }

    # Act
    response = client.post("/api/v1/vms", json=request_data)

    # Assert
    assert response.status_code == 200
    assert response.json()["name"] == "test-vm"

def test_list_vms_happy_path(client: TestClient, mock_vm_service: VMService):
    # Arrange
    vm_info = VMInfo(id="test-vm", name="test-vm", status=VMStatus.RUNNING, resources=VMResources(cpu=2, memory=2, storage=20))
    mock_vm_service.list_vms = AsyncMock(return_value=[vm_info])

    # Act
    response = client.get("/api/v1/vms")

    # Assert
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["name"] == "test-vm"

def test_get_vm_status_happy_path(client: TestClient, mock_vm_service: VMService):
    # Arrange
    vm_info = VMInfo(id="test-vm", name="test-vm", status=VMStatus.RUNNING, resources=VMResources(cpu=2, memory=2, storage=20))
    mock_vm_service.get_vm_status = AsyncMock(return_value=vm_info)

    # Act
    response = client.get("/api/v1/vms/test-vm")

    # Assert
    assert response.status_code == 200
    assert response.json()["name"] == "test-vm"

def test_delete_vm_happy_path(client: TestClient, mock_vm_service: VMService):
    # Arrange
    mock_vm_service.delete_vm = AsyncMock()

    # Act
    response = client.delete("/api/v1/vms/test-vm")

    # Assert
    assert response.status_code == 200
from provider.vm.models import VMNotFoundError

def test_create_vm_invalid_data(client: TestClient):
    # Arrange
    request_data = {
        "name": "test-vm",
        # "ssh_key" is missing
        "resources": {"cpu": 2, "memory": 2, "storage": 20}
    }

    # Act
    response = client.post("/api/v1/vms", json=request_data)

    # Assert
    assert response.status_code == 422  # Unprocessable Entity

def test_get_vm_status_not_found(client: TestClient, mock_vm_service: VMService):
    # Arrange
    mock_vm_service.get_vm_status = AsyncMock(side_effect=VMNotFoundError("VM not found"))

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
    mock_vm_service.create_vm = AsyncMock(side_effect=Exception("Internal Server Error"))
    request_data = {
        "name": "test-vm",
        "ssh_key": "ssh-rsa AAA...",
        "resources": {"cpu": 2, "memory": 2, "storage": 20}
    }

    # Act
    response = client.post("/api/v1/vms", json=request_data)

    # Assert
    assert response.status_code == 500
    assert response.json()["detail"] == "An unexpected error occurred"

def test_get_vm_status_service_exception(client: TestClient, mock_vm_service: VMService):
    # Arrange
    mock_vm_service.get_vm_status = AsyncMock(side_effect=Exception("Internal Server Error"))

    # Act
    response = client.get("/api/v1/vms/test-vm")

    # Assert
    assert response.status_code == 500
    assert response.json()["detail"] == "An unexpected error occurred"

def test_delete_vm_service_exception(client: TestClient, mock_vm_service: VMService):
    # Arrange
    mock_vm_service.delete_vm = AsyncMock(side_effect=Exception("Internal Server Error"))

    # Act
    response = client.delete("/api/v1/vms/test-vm")

    # Assert
    assert response.status_code == 500
    assert response.json()["detail"] == "An unexpected error occurred"

def test_list_vms_service_exception(client: TestClient, mock_vm_service: VMService):
    # Arrange
    mock_vm_service.list_vms = AsyncMock(side_effect=Exception("Internal Server Error"))

    # Act
    response = client.get("/api/v1/vms")

    # Assert
    assert response.status_code == 500
    assert response.json()["detail"] == "An unexpected error occurred"

@pytest.mark.parametrize("payload", [
    {"name": "test-vm", "ssh_key": "ssh-rsa AAA...", "resources": {"cpu": -1, "memory": 2, "storage": 20}},
    {"name": "test-vm", "ssh_key": "ssh-rsa AAA...", "resources": {"cpu": 2, "memory": -1, "storage": 20}},
    {"name": "test-vm", "ssh_key": "ssh-rsa AAA...", "resources": {"cpu": 2, "memory": 2, "storage": -1}},
])
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
        "resources": {"cpu": 2, "memory": 2, "storage": 20}
    }

    # Act
    response = client.post("/api/v1/vms", json=request_data)

    # Assert
    assert response.status_code == 422  # Unprocessable Entity
