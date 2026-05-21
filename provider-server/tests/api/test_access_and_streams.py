from unittest.mock import AsyncMock

import pytest
from dependency_injector import providers
from fastapi.testclient import TestClient

from provider.main import app
from provider.vm.models import MULTIPASS_SSH_USER, VMInfo, VMResources, VMStatus
from provider.vm.multipass_adapter import MultipassError


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class DummyStreamMap:
    def __init__(self, items=None):
        self._items = items or {}
        self.set_calls = []
        self.remove_calls = []

    async def set(self, vm_id, stream_id, requestor_address=None):
        self.set_calls.append((vm_id, stream_id, requestor_address))

    async def remove(self, vm_id):
        self.remove_calls.append(vm_id)

    async def get(self, vm_id):
        return self._items.get(vm_id)

    async def all_items(self):
        # Return a copy to avoid accidental external mutation
        return dict(self._items)

    async def active_items(self):
        return dict(self._items)

    async def get_record(self, vm_id):
        stream_id = self._items.get(vm_id)
        if stream_id is None:
            return None
        return {
            "vm_id": vm_id,
            "stream_id": stream_id,
            "requestor_address": "0xrequestor",
            "state": "active",
            "terminated_by": None,
            "termination_reason": None,
            "terminated_at": None,
            "settlement_tx_hash": None,
            "cleanup_state": None,
        }


def _enable_streaming_config():
    old = dict(app.container.config())
    cfg = dict(old)
    cfg.update(
        {
            "STREAM_PAYMENT_ADDRESS": "0x1111111111111111111111111111111111111111",
            "PAYMENTS_RPC_URL": "http://localhost",
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
        assert data["ssh_user"] == MULTIPASS_SSH_USER
        assert data["vm_id"] == "test-vm"
        assert data["multipass_name"] == "test-vm-20250101"
    finally:
        app.container.stream_map.reset_override()
        app.container.config.override(old)


def test_get_vm_access_missing_public_ip_fails_visibly(client: TestClient):
    vm_info = VMInfo(
        id="test-vm",
        name="test-vm",
        status=VMStatus.RUNNING,
        resources=VMResources(cpu=1, memory=1, storage=10),
        ssh_port=2222,
    )
    app.container.vm_service().get_vm_status = AsyncMock(return_value=vm_info)
    app.container.vm_service().name_mapper.get_multipass_name = AsyncMock(
        return_value="test-vm-20250101"
    )
    old = dict(app.container.config())
    cfg = dict(old)
    cfg.update({"PUBLIC_IP": None})
    try:
        app.container.config.override(cfg)
        resp = client.get("/api/v1/vms/test-vm/access")
        assert resp.status_code == 500
        assert resp.json() == {
            "detail": "provider public IP is not configured; cannot return SSH access"
        }
    finally:
        app.container.config.override(old)


def test_get_vm_access_auto_public_ip_fails_visibly(client: TestClient):
    vm_info = VMInfo(
        id="test-vm",
        name="test-vm",
        status=VMStatus.RUNNING,
        resources=VMResources(cpu=1, memory=1, storage=10),
        ssh_port=2222,
    )
    app.container.vm_service().get_vm_status = AsyncMock(return_value=vm_info)
    app.container.vm_service().name_mapper.get_multipass_name = AsyncMock(
        return_value="test-vm-20250101"
    )
    old = dict(app.container.config())
    cfg = dict(old)
    cfg.update({"PUBLIC_IP": "auto"})
    try:
        app.container.config.override(cfg)
        resp = client.get("/api/v1/vms/test-vm/access")
        assert resp.status_code == 500
        assert resp.json() == {
            "detail": "provider public IP is not configured; cannot return SSH access"
        }
    finally:
        app.container.config.override(old)


@pytest.mark.parametrize("public_ip", ["localhost", "127.0.0.1", "192.168.1.10"])
def test_get_vm_access_non_public_ip_fails_visibly(
    public_ip: str, client: TestClient
):
    vm_info = VMInfo(
        id="test-vm",
        name="test-vm",
        status=VMStatus.RUNNING,
        resources=VMResources(cpu=1, memory=1, storage=10),
        ssh_port=2222,
    )
    app.container.vm_service().get_vm_status = AsyncMock(return_value=vm_info)
    app.container.vm_service().name_mapper.get_multipass_name = AsyncMock(
        return_value="test-vm-20250101"
    )
    old = dict(app.container.config())
    cfg = dict(old)
    cfg.update({"ENVIRONMENT": "production", "PUBLIC_IP": public_ip})
    try:
        app.container.config.override(cfg)
        resp = client.get("/api/v1/vms/test-vm/access")
        assert resp.status_code == 500
        assert resp.json() == {
            "detail": "provider public IP must be a public address; cannot return SSH access"
        }
    finally:
        app.container.config.override(old)


def test_get_vm_access_pending_includes_ssh_user(client: TestClient):
    vm_info = VMInfo(
        id="test-vm",
        name="test-vm",
        status=VMStatus.CREATING,
        resources=VMResources(cpu=1, memory=1, storage=10),
        ssh_port=None,
    )
    app.container.vm_service().get_vm_status = AsyncMock(return_value=vm_info)
    app.container.vm_service().name_mapper.get_multipass_name = AsyncMock(
        return_value="test-vm-20250101"
    )

    resp = client.get("/api/v1/vms/test-vm/access")

    assert resp.status_code == 202
    data = resp.json()
    assert data["ssh_port"] is None
    assert data["ssh_user"] == MULTIPASS_SSH_USER


def test_get_vm_access_vm_not_found(monkeypatch, client: TestClient):
    app.container.vm_service().get_vm_status = AsyncMock(return_value=None)
    resp = client.get("/api/v1/vms/unknown/access")
    assert resp.status_code == 404


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
    assert resp.status_code == 404


def test_get_vm_access_multipass_error(monkeypatch, client: TestClient):
    app.container.vm_service().get_vm_status = AsyncMock(
        side_effect=MultipassError("mp error")
    )
    resp = client.get("/api/v1/vms/test-vm/access")
    assert resp.status_code == 502


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
        app.container.stream_map.reset_override()
        app.container.config.override(old)


def test_get_vm_stream_status_lookup_failure(monkeypatch, client: TestClient):
    old = _enable_streaming_config()
    try:
        app.container.stream_map.override(DummyStreamMap({"test-vm": 42}))

        # Dummy reader that raises on get_stream
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

        app.container.stream_reader.override(providers.Factory(BadReader))

        resp = client.get("/api/v1/vms/test-vm/stream")
        assert resp.status_code == 502
    finally:
        app.container.stream_reader.reset_override()
        app.container.stream_map.reset_override()
        app.container.config.override(old)


def test_get_vm_stream_status_happy_path(monkeypatch, client: TestClient):
    old = _enable_streaming_config()
    try:
        app.container.stream_map.override(DummyStreamMap({"test-vm": 7}))

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
                    "providerRatePerSecond": 2,
                    "providerDeposit": 400,
                    "providerWithdrawn": 50,
                    "donationBps": 150,
                    "donationRecipient": "0x94153E31AA476cE30C3AF64C255C623f80920BfF",
                    "donationDeposit": int(400 * 150 / 10000),
                    "donationWithdrawn": 0,
                    "leaseId": "0x" + "11" * 32,
                    "termsHash": "0x" + "22" * 32,
                }

            def verify_stream(self, sid, expected_recipient, *args):
                assert sid == 7
                return True, "ok"

        app.container.stream_reader.override(providers.Factory(GoodReader))

        resp = client.get("/api/v1/vms/test-vm/stream")
        assert resp.status_code == 200
        data = resp.json()
        assert data["vm_id"] == "test-vm"
        assert data["stream_id"] == 7
        assert data["verified"] is True
        assert data["payment_state"] == "active"
        # computed checks
        assert data["computed"]["now"] == 200
        assert data["computed"]["remaining_seconds"] == 100
        assert data["computed"]["provider_vested_wei"] == 200
        assert data["computed"]["donation_vested_wei"] == 3
        assert data["computed"]["vested_wei"] == 203
        assert data["computed"]["provider_withdrawable_wei"] == 150
        assert data["computed"]["donation_withdrawable_wei"] == 3
        assert data["computed"]["withdrawable_wei"] == 153
    finally:
        app.container.stream_reader.reset_override()
        app.container.stream_map.reset_override()
        app.container.config.override(old)


def test_get_vm_stream_status_reports_grace_state(client: TestClient):
    old = _enable_streaming_config()
    try:
        app.container.stream_map.override(DummyStreamMap({"test-vm": 7}))

        class GraceReader:
            def __init__(self, *a, **kw):
                class W3:
                    class Eth:
                        def get_block(self, *_):
                            return {"timestamp": 305}

                    eth = Eth()

                self.web3 = W3()

            def get_stream(self, sid):
                return {
                    "token": "0xT",
                    "sender": "0xS",
                    "recipient": app.container.config()["PROVIDER_ID"],
                    "startTime": 100,
                    "stopTime": 300,
                    "providerRatePerSecond": 2,
                    "providerDeposit": 400,
                    "providerWithdrawn": 50,
                    "donationBps": 150,
                    "donationRecipient": "0x94153E31AA476cE30C3AF64C255C623f80920BfF",
                    "donationDeposit": int(400 * 150 / 10000),
                    "donationWithdrawn": 0,
                    "leaseId": "0x" + "11" * 32,
                    "termsHash": "0x" + "22" * 32,
                }

            def verify_stream(self, sid, expected_recipient, *args):
                return False, "stream expired"

        app.container.stream_reader.override(providers.Factory(GraceReader))

        resp = client.get("/api/v1/vms/test-vm/stream")
        assert resp.status_code == 200
        data = resp.json()
        assert data["computed"]["remaining_seconds"] == 0
        assert data["payment_state"] == "grace"
    finally:
        app.container.stream_reader.reset_override()
        app.container.stream_map.reset_override()
        app.container.config.override(old)


def test_get_vm_stream_status_falls_back_when_stream_state_reverts(client: TestClient):
    old = _enable_streaming_config()
    try:
        app.container.stream_map.override(DummyStreamMap({"test-vm": 7}))

        class RevertingStateReader:
            def __init__(self, *a, **kw):
                class W3:
                    class Eth:
                        def get_block(self, *_):
                            return {"timestamp": 305}

                    eth = Eth()

                self.web3 = W3()

            def get_stream(self, sid):
                return {
                    "token": "0xT",
                    "sender": "0xS",
                    "recipient": app.container.config()["PROVIDER_ID"],
                    "startTime": 100,
                    "stopTime": 300,
                    "providerRatePerSecond": 2,
                    "providerDeposit": 400,
                    "providerWithdrawn": 50,
                    "donationBps": 150,
                    "donationRecipient": "0x94153E31AA476cE30C3AF64C255C623f80920BfF",
                    "donationDeposit": int(400 * 150 / 10000),
                    "donationWithdrawn": 0,
                    "leaseId": "0x" + "11" * 32,
                    "termsHash": "0x" + "22" * 32,
                }

            def verify_stream(self, sid, expected_recipient, *args):
                return False, "stream expired"

            def stream_state(self, sid):
                raise RuntimeError("execution reverted")

        app.container.stream_reader.override(providers.Factory(RevertingStateReader))

        resp = client.get("/api/v1/vms/test-vm/stream")
        assert resp.status_code == 200
        data = resp.json()
        assert data["computed"]["remaining_seconds"] == 0
        assert data["payment_state"] == "grace"
    finally:
        app.container.stream_reader.reset_override()
        app.container.stream_map.reset_override()
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
                    "providerRatePerSecond": 1,
                    "providerDeposit": 600,
                    "providerWithdrawn": 10,
                    "donationBps": 150,
                    "donationRecipient": "0x94153E31AA476cE30C3AF64C255C623f80920BfF",
                    "donationDeposit": int(600 * 150 / 10000),
                    "donationWithdrawn": 0,
                    "leaseId": "0x" + "11" * 32,
                    "termsHash": "0x" + "22" * 32,
                }

            def verify_stream(self, sid, expected_recipient, *args):
                return True, "ok"

        app.container.stream_reader.override(providers.Factory(Reader))

        resp = client.get("/api/v1/payments/streams")
        assert resp.status_code == 502
    finally:
        app.container.stream_reader.reset_override()
        app.container.stream_map.reset_override()
        app.container.config.override(old)
