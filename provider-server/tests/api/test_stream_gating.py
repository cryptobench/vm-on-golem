import pytest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient

from provider.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_create_vm_requires_stream_when_enabled(monkeypatch, client: TestClient):
    # Enable payments by setting non-zero contract and provider id
    old = dict(app.container.config())
    cfg = dict(old)
    cfg.update({
        "STREAM_PAYMENT_ADDRESS": "0x1111111111111111111111111111111111111111",
        "POLYGON_RPC_URL": "http://localhost",
        "PROVIDER_ID": "0x2222222222222222222222222222222222222222",
    })
    try:
        app.container.config.override(cfg)
        # Without stream_id
        request_data = {
            "name": "test-vm",
            "ssh_key": "ssh-rsa AAA...",
            "resources": {"cpu": 1, "memory": 1, "storage": 10}
        }
        resp = client.post("/api/v1/vms", json=request_data)
        assert resp.status_code == 400
        assert "stream_id" in resp.json()["detail"]
    finally:
        app.container.config.override(old)


def test_create_vm_accepts_valid_stream(monkeypatch, client: TestClient):
    # Enable payments
    old = dict(app.container.config())
    cfg = dict(old)
    cfg.update({
        "STREAM_PAYMENT_ADDRESS": "0x1111111111111111111111111111111111111111",
        "POLYGON_RPC_URL": "http://localhost",
        "PROVIDER_ID": "0x2222222222222222222222222222222222222222",
    })
    try:
        app.container.config.override(cfg)
        # Patch reader to always verify ok
        from provider.api import routes as routes_mod

        class DummyReader:
            def __init__(self, *a, **kw):
                pass
            def verify_stream(self, stream_id, expected_recipient):
                return True, "ok"

        monkeypatch.setattr(routes_mod, "StreamPaymentReader", DummyReader)

        # Patch vm service to return a dummy VM
        from provider.vm.models import VMInfo, VMResources, VMStatus
        vm_info = VMInfo(id="test-vm", name="test-vm", status=VMStatus.RUNNING, resources=VMResources(cpu=1, memory=1, storage=10))
        app.container.vm_service().create_vm = AsyncMock(return_value=vm_info)

        request_data = {
            "name": "test-vm",
            "ssh_key": "ssh-rsa AAA...",
            "resources": {"cpu": 1, "memory": 1, "storage": 10},
            "stream_id": 123
        }
        resp = client.post("/api/v1/vms", json=request_data)
        assert resp.status_code == 200
        assert resp.json()["name"] == "test-vm"
    finally:
        app.container.config.override(old)


def test_create_vm_rejects_invalid_stream(monkeypatch, client: TestClient):
    old = dict(app.container.config())
    cfg = dict(old)
    cfg.update({
        "STREAM_PAYMENT_ADDRESS": "0x1111111111111111111111111111111111111111",
        "POLYGON_RPC_URL": "http://localhost",
        "PROVIDER_ID": "0x2222222222222222222222222222222222222222",
    })
    try:
        app.container.config.override(cfg)
        from provider.api import routes as routes_mod

        class DummyReaderBad:
            def __init__(self, *a, **kw):
                pass
            def verify_stream(self, stream_id, expected_recipient):
                return False, "recipient mismatch"

        monkeypatch.setattr(routes_mod, "StreamPaymentReader", DummyReaderBad)

        request_data = {
            "name": "test-vm",
            "ssh_key": "ssh-rsa AAA...",
            "resources": {"cpu": 1, "memory": 1, "storage": 10},
            "stream_id": 123
        }
        resp = client.post("/api/v1/vms", json=request_data)
        assert resp.status_code == 400
        assert "invalid stream" in resp.json()["detail"]
    finally:
        app.container.config.override(old)
