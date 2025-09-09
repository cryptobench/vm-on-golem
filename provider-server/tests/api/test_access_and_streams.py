import pytest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient

from provider.main import app
from provider.vm.models import VMInfo, VMResources, VMStatus
from provider.vm.multipass_adapter import MultipassError


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class DummyStreamMap:
    def __init__(self, items=None):
        self._items = items or {}
        self.set_calls = []
        self.remove_calls = []

    async def set(self, vm_id, stream_id):
        self.set_calls.append((vm_id, stream_id))

    async def remove(self, vm_id):
        self.remove_calls.append(vm_id)

    async def get(self, vm_id):
        return self._items.get(vm_id)

    async def all_items(self):
        # Return a copy to avoid accidental external mutation
        return dict(self._items)


def _enable_streaming_config():
    old = dict(app.container.config())
    cfg = dict(old)
    cfg.update(
        {
            "STREAM_PAYMENT_ADDRESS": "0x1111111111111111111111111111111111111111",
            "POLYGON_RPC_URL": "http://localhost",
            "PROVIDER_ID": "0x2222222222222222222222222222222222222222",
        }
    )
    app.container.config.override(cfg)
    return old


def test_get_vm_access_happy_path(monkeypatch, client: TestClient):
    vm_info = VMInfo(
        id="test-vm",
        name="test-vm",
        status=VMStatus.RUNNING,
        resources=VMResources(cpu=1, memory=1, storage=10),
        ssh_port=2222,
    )
    app.container.vm_service().get_vm_status = AsyncMock(return_value=vm_info)
    # Provide name mapping
    app.container.vm_service().name_mapper.get_multipass_name = AsyncMock(
        return_value="test-vm-20250101"
    )
    # Ensure PUBLIC_IP is set in config for response
    old = dict(app.container.config())
    cfg = dict(old)
    cfg.update({"PUBLIC_IP": "1.2.3.4"})
    try:
        app.container.config.override(cfg)
        resp = client.get("/api/v1/vms/test-vm/access")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ssh_host"] == "1.2.3.4"
        assert data["ssh_port"] == 2222
        assert data["vm_id"] == "test-vm"
        assert data["multipass_name"] == "test-vm-20250101"
    finally:
        app.container.config.override(old)


def test_get_vm_access_vm_not_found(monkeypatch, client: TestClient):
    app.container.vm_service().get_vm_status = AsyncMock(return_value=None)
    resp = client.get("/api/v1/vms/unknown/access")
    # Current implementation wraps HTTPException into generic 500
    assert resp.status_code == 500


def test_get_vm_access_mapping_not_found(monkeypatch, client: TestClient):
    vm_info = VMInfo(
        id="test-vm",
        name="test-vm",
        status=VMStatus.RUNNING,
        resources=VMResources(cpu=1, memory=1, storage=10),
        ssh_port=2222,
    )
    app.container.vm_service().get_vm_status = AsyncMock(return_value=vm_info)
    app.container.vm_service().name_mapper.get_multipass_name = AsyncMock(
        return_value=None
    )
    resp = client.get("/api/v1/vms/test-vm/access")
    # Current implementation wraps HTTPException into generic 500
    assert resp.status_code == 500


def test_get_vm_access_multipass_error(monkeypatch, client: TestClient):
    app.container.vm_service().get_vm_status = AsyncMock(
        side_effect=MultipassError("mp error")
    )
    resp = client.get("/api/v1/vms/test-vm/access")
    assert resp.status_code == 500


def test_get_vm_stream_status_disabled(client: TestClient):
    # Force-disable streaming by overriding to zero address
    old = dict(app.container.config())
    cfg = dict(old)
    cfg.update({"STREAM_PAYMENT_ADDRESS": "0x0000000000000000000000000000000000000000"})
    try:
        app.container.config.override(cfg)
        resp = client.get("/api/v1/vms/test-vm/stream")
        assert resp.status_code == 400
    finally:
        app.container.config.override(old)


def test_get_vm_stream_status_no_mapping(monkeypatch, client: TestClient):
    old = _enable_streaming_config()
    try:
        app.container.stream_map.override(DummyStreamMap({}))
        resp = client.get("/api/v1/vms/test-vm/stream")
        assert resp.status_code == 404
    finally:
        app.container.config.override(old)


def test_get_vm_stream_status_lookup_failure(monkeypatch, client: TestClient):
    old = _enable_streaming_config()
    try:
        app.container.stream_map.override(DummyStreamMap({"test-vm": 42}))

        # Dummy reader that raises on get_stream
        from provider.api import routes as routes_mod

        class BadReader:
            def __init__(self, *a, **kw):
                class W3:
                    class Eth:
                        def get_block(self, *_):
                            return {"timestamp": 1234567890}

                    eth = Eth()

                self.web3 = W3()

            def get_stream(self, *_):
                raise RuntimeError("boom")

            def verify_stream(self, *_):
                return True, "ok"

        monkeypatch.setattr(routes_mod, "StreamPaymentReader", BadReader)

        resp = client.get("/api/v1/vms/test-vm/stream")
        assert resp.status_code == 502
    finally:
        app.container.config.override(old)


def test_get_vm_stream_status_happy_path(monkeypatch, client: TestClient):
    old = _enable_streaming_config()
    try:
        app.container.stream_map.override(DummyStreamMap({"test-vm": 7}))

        from provider.api import routes as routes_mod

        class GoodReader:
            def __init__(self, *a, **kw):
                class W3:
                    class Eth:
                        def get_block(self, *_):
                            return {"timestamp": 200}

                    eth = Eth()

                self.web3 = W3()

            def get_stream(self, sid):
                assert sid == 7
                return {
                    "token": "0xT",
                    "sender": "0xS",
                    "recipient": app.container.config()["PROVIDER_ID"],
                    "startTime": 100,
                    "stopTime": 300,
                    "ratePerSecond": 2,
                    "deposit": 400,
                    "withdrawn": 50,
                    "halted": False,
                }

            def verify_stream(self, sid, expected_recipient):
                assert sid == 7
                return True, "ok"

        monkeypatch.setattr(routes_mod, "StreamPaymentReader", GoodReader)

        resp = client.get("/api/v1/vms/test-vm/stream")
        assert resp.status_code == 200
        data = resp.json()
        assert data["vm_id"] == "test-vm"
        assert data["stream_id"] == 7
        assert data["verified"] is True
        # computed checks
        assert data["computed"]["now"] == 200
        assert data["computed"]["remaining_seconds"] == 100
        # vested = (min(200,300)-100)*2 = 200
        assert data["computed"]["vested_wei"] == 200
        # withdrawable = max(vested - withdrawn, 0) = 150
        assert data["computed"]["withdrawable_wei"] == 150
    finally:
        app.container.config.override(old)


def test_list_stream_statuses_disabled(client: TestClient):
    old = dict(app.container.config())
    cfg = dict(old)
    cfg.update({"STREAM_PAYMENT_ADDRESS": "0x0000000000000000000000000000000000000000"})
    try:
        app.container.config.override(cfg)
        resp = client.get("/api/v1/payments/streams")
        assert resp.status_code == 400
    finally:
        app.container.config.override(old)


def test_list_stream_statuses_happy_and_errors(monkeypatch, client: TestClient):
    old = _enable_streaming_config()
    try:
        # two items; one will fail
        app.container.stream_map.override(DummyStreamMap({"vmA": 1, "vmB": 2}))

        from provider.api import routes as routes_mod

        class Reader:
            def __init__(self, *a, **kw):
                class W3:
                    class Eth:
                        def get_block(self, *_):
                            return {"timestamp": 500}

                    eth = Eth()

                self.web3 = W3()

            def get_stream(self, sid):
                if sid == 2:
                    raise RuntimeError("fail")
                # for sid = 1
                return {
                    "token": "0xT",
                    "sender": "0xS",
                    "recipient": app.container.config()["PROVIDER_ID"],
                    "startTime": 100,
                    "stopTime": 700,
                    "ratePerSecond": 1,
                    "deposit": 600,
                    "withdrawn": 10,
                    "halted": False,
                }

            def verify_stream(self, sid, expected_recipient):
                return True, "ok"

        monkeypatch.setattr(routes_mod, "StreamPaymentReader", Reader)

        resp = client.get("/api/v1/payments/streams")
        assert resp.status_code == 200
        rows = resp.json()
        # one succeeded, one skipped due to error
        assert len(rows) == 1
        r = rows[0]
        assert r["vm_id"] == "vmA"
        assert r["stream_id"] == 1
        assert r["verified"] is True
        assert r["computed"]["remaining_seconds"] == 200
    finally:
        app.container.config.override(old)
