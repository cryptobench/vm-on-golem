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
            def get_stream(self, *_):
                return {
                    "token": "0xT",
                    "sender": "0xS",
                    "recipient": cfg["PROVIDER_ID"],
                    "startTime": 100,
                    "stopTime": 200,
                    "ratePerSecond": 1,
                    "deposit": 100,
                    "withdrawn": 10,
                    "halted": False,
                }
            @property
            def web3(self):
                class W3:
                    class Eth:
                        def get_block(self, *_):
                            return {"timestamp": 150}
                    eth = Eth()
                return W3()

        monkeypatch.setattr(routes_mod, "StreamPaymentReader", DummyReader)

        # Patch vm service to return a dummy VM and capture stream_map.set
        from provider.vm.models import VMInfo, VMResources, VMStatus
        vm_info = VMInfo(id="test-vm", name="test-vm", status=VMStatus.RUNNING, resources=VMResources(cpu=1, memory=1, storage=10))
        app.container.vm_service().create_vm = AsyncMock(return_value=vm_info)

        # Replace stream_map with a dummy that records set/remove
        class DummyStreamMap:
            def __init__(self):
                self.set_calls = []
                self.remove_calls = []
            async def set(self, vm_id, stream_id):
                self.set_calls.append((vm_id, stream_id))
            async def remove(self, vm_id):
                self.remove_calls.append(vm_id)
            async def all_items(self):
                return {}
        dummy_map = DummyStreamMap()
        app.container.stream_map.override(dummy_map)

        request_data = {
            "name": "test-vm",
            "ssh_key": "ssh-rsa AAA...",
            "resources": {"cpu": 1, "memory": 1, "storage": 10},
            "stream_id": 123
        }
        resp = client.post("/api/v1/vms", json=request_data)
        assert resp.status_code == 200
        assert resp.json()["name"] == "test-vm"
        # mapping persisted
        assert dummy_map.set_calls == [("test-vm", 123)]
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


def test_create_vm_gating_respects_default_deploy_in_pytest(monkeypatch, client: TestClient):
    # When running under pytest and SPA equals default deployment SPA, gating should not enforce
    old = dict(app.container.config())
    cfg = dict(old)
    cfg.update({
        "STREAM_PAYMENT_ADDRESS": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "POLYGON_RPC_URL": "http://localhost",
        "PROVIDER_ID": "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    })
    try:
        app.container.config.override(cfg)
        from provider.api import routes as routes_mod
        # Pretend default deployment returns same SPA, so gating is skipped in tests
        monkeypatch.setattr(routes_mod._Cfg, "_load_l2_deployment", lambda: (cfg["STREAM_PAYMENT_ADDRESS"], "0xGLM"))

        # vm service returns a dummy VM
        from provider.vm.models import VMInfo, VMResources, VMStatus
        vm_info = VMInfo(id="vmx", name="vmx", status=VMStatus.RUNNING, resources=VMResources(cpu=1, memory=1, storage=10))
        app.container.vm_service().create_vm = AsyncMock(return_value=vm_info)

        req = {
            "name": "vmx",
            "ssh_key": "ssh-rsa AAA...",
            "resources": {"cpu": 1, "memory": 1, "storage": 10},
            # no stream_id as gating should be skipped
        }
        resp = client.post("/api/v1/vms", json=req)
        assert resp.status_code == 200
    finally:
        app.container.config.override(old)


def test_create_vm_gating_when_default_lookup_fails_enforces(monkeypatch, client: TestClient):
    # Enable payments and make default-load fail; gating should enforce and demand stream_id
    old = dict(app.container.config())
    cfg = dict(old)
    cfg.update({
        "STREAM_PAYMENT_ADDRESS": "0x9999999999999999999999999999999999999999",
        "POLYGON_RPC_URL": "http://localhost",
        "PROVIDER_ID": "0x8888888888888888888888888888888888888888",
    })
    try:
        app.container.config.override(cfg)
        from provider.api import routes as routes_mod
        # Force load failure
        def boom():
            raise RuntimeError("no deployment")
        monkeypatch.setattr(routes_mod._Cfg, "_load_l2_deployment", boom)

        req = {
            "name": "vmz",
            "ssh_key": "ssh-rsa AAA...",
            "resources": {"cpu": 1, "memory": 1, "storage": 10},
            # no stream_id (should 400)
        }
        resp = client.post("/api/v1/vms", json=req)
        assert resp.status_code == 400
    finally:
        app.container.config.override(old)


def test_create_vm_multipass_error(monkeypatch, client: TestClient):
    # Trigger create_vm to raise MultipassError and map to 500
    from provider.vm.multipass_adapter import MultipassError
    app.container.vm_service().create_vm = AsyncMock(side_effect=MultipassError("mp failed"))
    req = {
        "name": "vmq",
        "ssh_key": "ssh-rsa AAA...",
        "resources": {"cpu": 1, "memory": 1, "storage": 10},
    }
    resp = client.post("/api/v1/vms", json=req)
    assert resp.status_code == 500


def test_create_vm_enforces_outside_pytest_env(monkeypatch, client: TestClient):
    # Simulate non-pytest environment path for gating logic (covers else branch)
    old = dict(app.container.config())
    cfg = dict(old)
    cfg.update({
        "STREAM_PAYMENT_ADDRESS": "0x4444444444444444444444444444444444444444",
        "POLYGON_RPC_URL": "http://localhost",
        "PROVIDER_ID": "0x5555555555555555555555555555555555555555",
    })
    try:
        app.container.config.override(cfg)
        # Temporarily remove PYTEST_CURRENT_TEST to exercise else path
        import os as _os
        existed = "PYTEST_CURRENT_TEST" in _os.environ
        val = _os.environ.pop("PYTEST_CURRENT_TEST", None)
        try:
            req = {
                "name": "vmo",
                "ssh_key": "ssh-rsa AAA...",
                "resources": {"cpu": 1, "memory": 1, "storage": 10},
            }
            resp = client.post("/api/v1/vms", json=req)
            assert resp.status_code == 400
        finally:
            if existed:
                _os.environ["PYTEST_CURRENT_TEST"] = val or "x"
    finally:
        app.container.config.override(old)

def test_create_vm_logs_when_stream_map_set_fails(monkeypatch, client: TestClient):
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

        class Reader:
            def __init__(self, *a, **kw):
                pass
            def verify_stream(self, *_):
                return True, "ok"

        monkeypatch.setattr(routes_mod, "StreamPaymentReader", Reader)

        # vm service returns a dummy VM
        from provider.vm.models import VMInfo, VMResources, VMStatus
        vm_info = VMInfo(id="vmy", name="vmy", status=VMStatus.RUNNING, resources=VMResources(cpu=1, memory=1, storage=10))
        app.container.vm_service().create_vm = AsyncMock(return_value=vm_info)

        # stream_map that raises on set
        class BadMap:
            async def set(self, *_):
                raise RuntimeError("fail")
        app.container.stream_map.override(BadMap())

        req = {
            "name": "vmy",
            "ssh_key": "ssh-rsa AAA...",
            "resources": {"cpu": 1, "memory": 1, "storage": 10},
            "stream_id": 9,
        }
        resp = client.post("/api/v1/vms", json=req)
        assert resp.status_code == 200
    finally:
        app.container.config.override(old)
