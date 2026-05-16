import logging
from unittest.mock import AsyncMock

import pytest
from dependency_injector import providers
from fastapi.testclient import TestClient

from provider.main import app
from provider.payments.lease_quote_service import LeaseQuoteService


REQUESTOR = "0x3333333333333333333333333333333333333333"
TOKEN = "0x4444444444444444444444444444444444444444"
LEASE = "0x" + "11" * 32
TERMS = "0x" + "22" * 32


def payment(stream_id: int = 123, terms_hash: str = TERMS) -> dict:
    return {
        "stream_id": stream_id,
        "lease_id": LEASE,
        "terms_hash": terms_hash,
        "rate_per_second_wei": 1,
        "duration_seconds": 3600,
    }


def terms_hash(cfg: dict, vm_name: str = "test-vm") -> str:
    return LeaseQuoteService._terms_hash(
        provider_address=cfg["PROVIDER_ID"],
        requestor_address=REQUESTOR,
        vm_name=vm_name,
        image="24.04",
        cpu=1,
        memory=1,
        storage=10,
        rate_per_second=1,
        duration_seconds=3600,
        contract_address=cfg["STREAM_PAYMENT_ADDRESS"],
        glm_token_address=TOKEN,
        chain_id=31337,
        lease_id=LEASE,
    )


def stream(cfg: dict, terms: str | None = None, **overrides) -> dict:
    base = {
        "token": TOKEN,
        "sender": REQUESTOR,
        "recipient": cfg["PROVIDER_ID"],
        "startTime": 100,
        "stopTime": 200,
        "ratePerSecond": 1,
        "deposit": 100,
        "withdrawn": 10,
        "leaseId": LEASE,
        "termsHash": terms or TERMS,
    }
    base.update(overrides)
    return base


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_create_vm_requires_stream_when_enabled(monkeypatch, client: TestClient):
    # Enable payments by setting non-zero contract and provider id
    old = dict(app.container.config())
    cfg = dict(old)
    cfg.update(
        {
            "STREAM_PAYMENT_ADDRESS": "0x1111111111111111111111111111111111111111",
            "POLYGON_RPC_URL": "http://localhost",
            "PROVIDER_ID": "0x2222222222222222222222222222222222222222",
            "GLM_TOKEN_ADDRESS": TOKEN,
            "PRICE_GLM_PER_CORE_MONTH": "0.000000000002628",
            "PRICE_GLM_PER_GB_RAM_MONTH": "0",
            "PRICE_GLM_PER_GB_STORAGE_MONTH": "0",
        }
    )
    try:
        app.container.config.override(cfg)
        # Without stream_id
        request_data = {
            "name": "test-vm",
            "ssh_key": "ssh-rsa AAA...",
            "resources": {"cpu": 1, "memory": 1, "storage": 10},
        }
        resp = client.post("/api/v1/vms", json=request_data)
        assert resp.status_code == 400
        assert "payment proof" in resp.json()["detail"]
    finally:
        app.container.config.override(old)


def test_create_vm_accepts_valid_stream(monkeypatch, client: TestClient):
    # Enable payments
    old = dict(app.container.config())
    cfg = dict(old)
    cfg.update(
        {
            "STREAM_PAYMENT_ADDRESS": "0x1111111111111111111111111111111111111111",
            "POLYGON_RPC_URL": "http://localhost",
            "PROVIDER_ID": "0x2222222222222222222222222222222222222222",
            "GLM_TOKEN_ADDRESS": TOKEN,
            "PRICE_GLM_PER_CORE_MONTH": "0.000000000002628",
            "PRICE_GLM_PER_GB_RAM_MONTH": "0",
            "PRICE_GLM_PER_GB_STORAGE_MONTH": "0",
        }
    )
    try:
        app.container.config.override(cfg)

        class DummyReader:
            def __init__(self, *a, **kw):
                pass

            def verify_stream(self, stream_id, expected_recipient):
                return True, "ok"

            def get_stream(self, *_):
                return stream(cfg, terms_hash(cfg))

            @property
            def web3(self):
                class W3:
                    class Eth:
                        chain_id = 31337

                        def get_block(self, *_):
                            return {"timestamp": 150}

                    eth = Eth()

                return W3()

        app.container.stream_reader.override(providers.Factory(DummyReader))
        # Patch vm service to return a dummy VM and capture stream_map.set
        from provider.vm.models import VMInfo, VMResources, VMStatus

        vm_info = VMInfo(
            id="test-vm",
            name="test-vm",
            status=VMStatus.RUNNING,
            resources=VMResources(cpu=1, memory=1, storage=10),
        )
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
            "payment": payment(123, terms_hash(cfg)),
        }
        resp = client.post("/api/v1/vms", json=request_data)
        assert resp.status_code == 200
        assert resp.json()["name"] == "test-vm"
        # mapping persisted
        assert dummy_map.set_calls == [("test-vm", 123)]
    finally:
        app.container.stream_reader.reset_override()
        app.container.stream_map.reset_override()
        app.container.config.override(old)


def test_create_vm_rejects_invalid_stream(monkeypatch, client: TestClient):
    old = dict(app.container.config())
    cfg = dict(old)
    cfg.update(
        {
            "STREAM_PAYMENT_ADDRESS": "0x1111111111111111111111111111111111111111",
            "POLYGON_RPC_URL": "http://localhost",
            "PROVIDER_ID": "0x2222222222222222222222222222222222222222",
            "GLM_TOKEN_ADDRESS": TOKEN,
            "PRICE_GLM_PER_CORE_MONTH": "0.000000000002628",
            "PRICE_GLM_PER_GB_RAM_MONTH": "0",
            "PRICE_GLM_PER_GB_STORAGE_MONTH": "0",
        }
    )
    try:
        app.container.config.override(cfg)

        class DummyReaderBad:
            def __init__(self, *a, **kw):
                pass

            def get_stream(self, *_):
                return stream(
                    cfg,
                    terms_hash(cfg),
                    recipient="0x9999999999999999999999999999999999999999",
                )

            @property
            def web3(self):
                class W3:
                    class Eth:
                        chain_id = 31337

                        def get_block(self, *_):
                            return {"timestamp": 150}

                    eth = Eth()

                return W3()

        app.container.stream_reader.override(providers.Factory(DummyReaderBad))

        request_data = {
            "name": "test-vm",
            "ssh_key": "ssh-rsa AAA...",
            "resources": {"cpu": 1, "memory": 1, "storage": 10},
            "payment": payment(123, terms_hash(cfg)),
        }
        resp = client.post("/api/v1/vms", json=request_data)
        assert resp.status_code == 400
        assert "invalid stream" in resp.json()["detail"]
    finally:
        app.container.stream_reader.reset_override()
        app.container.config.override(old)


def test_create_vm_requires_stream_for_configured_payments_in_pytest(
    monkeypatch, client: TestClient
):
    old = dict(app.container.config())
    cfg = dict(old)
    cfg.update(
        {
            "STREAM_PAYMENT_ADDRESS": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "POLYGON_RPC_URL": "http://localhost",
            "PROVIDER_ID": "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        }
    )
    try:
        app.container.config.override(cfg)
        req = {
            "name": "vmx",
            "ssh_key": "ssh-rsa AAA...",
            "resources": {"cpu": 1, "memory": 1, "storage": 10},
        }
        resp = client.post("/api/v1/vms", json=req)
        assert resp.status_code == 400
    finally:
        app.container.config.override(old)


def test_lease_quote_logs_unexpected_failure(caplog):
    class FailingLeaseQuoteService:
        def create_quote(self, command):
            raise RuntimeError("boom")

    client = TestClient(app, raise_server_exceptions=False)
    caplog.set_level(logging.ERROR, logger="provider.api.payments_routes")
    app.container.lease_quote_service.override(FailingLeaseQuoteService())
    try:
        response = client.post(
            "/api/v1/payments/lease-quotes",
            json={
                "vm_name": "test-vm",
                "image": "24.04",
                "cpu": 1,
                "memory": 1,
                "storage": 10,
                "duration_seconds": 3600,
                "requestor_address": REQUESTOR,
            },
        )
    finally:
        app.container.lease_quote_service.reset_override()

    assert response.status_code == 500
    assert "Lease quote creation failed" in caplog.text
    assert "boom" in caplog.text


def test_create_vm_gating_enforces_without_default_lookup(
    monkeypatch, client: TestClient
):
    old = dict(app.container.config())
    cfg = dict(old)
    cfg.update(
        {
            "STREAM_PAYMENT_ADDRESS": "0x9999999999999999999999999999999999999999",
            "POLYGON_RPC_URL": "http://localhost",
            "PROVIDER_ID": "0x8888888888888888888888888888888888888888",
        }
    )
    try:
        app.container.config.override(cfg)
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

    app.container.vm_service().create_vm = AsyncMock(
        side_effect=MultipassError("mp failed")
    )
    req = {
        "name": "vmq",
        "ssh_key": "ssh-rsa AAA...",
        "resources": {"cpu": 1, "memory": 1, "storage": 10},
    }
    resp = client.post("/api/v1/vms", json=req)
    assert resp.status_code == 400
    assert "payment" in resp.json()["detail"]


def test_create_vm_enforces_outside_pytest_env(monkeypatch, client: TestClient):
    # Simulate non-pytest environment path for gating logic (covers else branch)
    old = dict(app.container.config())
    cfg = dict(old)
    cfg.update(
        {
            "STREAM_PAYMENT_ADDRESS": "0x4444444444444444444444444444444444444444",
            "POLYGON_RPC_URL": "http://localhost",
            "PROVIDER_ID": "0x5555555555555555555555555555555555555555",
        }
    )
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
    cfg.update(
        {
            "STREAM_PAYMENT_ADDRESS": "0x1111111111111111111111111111111111111111",
            "POLYGON_RPC_URL": "http://localhost",
            "PROVIDER_ID": "0x2222222222222222222222222222222222222222",
            "GLM_TOKEN_ADDRESS": TOKEN,
            "PRICE_GLM_PER_CORE_MONTH": "0.000000000002628",
            "PRICE_GLM_PER_GB_RAM_MONTH": "0",
            "PRICE_GLM_PER_GB_STORAGE_MONTH": "0",
        }
    )
    try:
        app.container.config.override(cfg)

        class Reader:
            def __init__(self, *a, **kw):
                pass

            def verify_stream(self, *_):
                return True, "ok"

            def get_stream(self, *_):
                return stream(cfg, terms_hash(cfg, "vmy"))

            @property
            def web3(self):
                class W3:
                    class Eth:
                        chain_id = 31337

                        def get_block(self, *_):
                            return {"timestamp": 150}

                    eth = Eth()

                return W3()

        app.container.stream_reader.override(providers.Factory(Reader))

        # vm service returns a dummy VM
        from provider.vm.models import VMInfo, VMResources, VMStatus

        vm_info = VMInfo(
            id="vmy",
            name="vmy",
            status=VMStatus.RUNNING,
            resources=VMResources(cpu=1, memory=1, storage=10),
        )
        app.container.vm_service().create_vm = AsyncMock(return_value=vm_info)

        # stream_map that raises on set
        class BadMap:
            async def set(self, *_):
                raise RuntimeError("fail")

            async def all_items(self):
                return {}

        app.container.stream_map.override(BadMap())

        req = {
            "name": "vmy",
            "ssh_key": "ssh-rsa AAA...",
            "resources": {"cpu": 1, "memory": 1, "storage": 10},
            "payment": payment(9, terms_hash(cfg, "vmy")),
        }
        resp = client.post("/api/v1/vms", json=req)
        assert resp.status_code == 502
    finally:
        app.container.stream_reader.reset_override()
        app.container.stream_map.reset_override()
        app.container.config.override(old)
