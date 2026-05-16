import time
from unittest.mock import AsyncMock

from eth_account import Account
from eth_account.messages import encode_typed_data
from fastapi.testclient import TestClient
import pytest

from provider.auth.services import (
    REQUESTOR_SESSION_DOMAIN,
    REQUESTOR_SESSION_VERSION,
    ProviderAuthService,
)
from provider.main import app
from provider.vm.models import VMInfo, VMResources, VMStatus

REQUESTOR_KEY = "0x" + "33" * 32
OTHER_KEY = "0x" + "44" * 32
REQUESTOR = Account.from_key(REQUESTOR_KEY).address
OTHER = Account.from_key(OTHER_KEY).address
PROVIDER = "0x2222222222222222222222222222222222222222"

VM_READ_ENDPOINTS = [
    "/api/v1/vms/vm-a",
    "/api/v1/vms/vm-a/access",
    "/api/v1/vms/vm-a/snapshots",
    "/api/v1/vms/vm-a/stream",
    "/api/v1/vms/vm-a/metrics/latest",
    "/api/v1/vms/vm-a/metrics/history",
]

VM_WRITE_ENDPOINTS = [
    ("POST", "/api/v1/vms/vm-a/start", {}),
    ("POST", "/api/v1/vms/vm-a/stop", {}),
    ("POST", "/api/v1/vms/vm-a/restart", {}),
    ("POST", "/api/v1/vms/vm-a/suspend", {}),
    ("POST", "/api/v1/vms/vm-a/resume", {}),
    (
        "POST",
        "/api/v1/vms/vm-a/resize",
        {"resources": {"cpu": 1, "memory": 1, "storage": 10}},
    ),
    ("POST", "/api/v1/vms/vm-a/snapshots", {}),
    ("POST", "/api/v1/vms/vm-a/snapshots/snap-a/restore", {}),
    ("DELETE", "/api/v1/vms/vm-a/snapshots/snap-a", None),
    ("POST", "/api/v1/vms/vm-a/clone", {"new_name": "vm-b"}),
    ("DELETE", "/api/v1/vms/vm-a", None),
]


class FakeStreamMap:
    def __init__(self, owner: str | None, stream_id: int | None = 1):
        self.owner = owner
        self.stream_id = stream_id

    async def get_owner(self, vm_id: str):
        return self.owner

    async def get(self, vm_id: str):
        return self.stream_id


class FakeJobStore:
    async def get_job(self, job_id: str):
        return {
            "job_id": job_id,
            "vm_id": "vm-a",
            "requestor_address": REQUESTOR,
            "status": "queued",
            "lifecycle_stage": "queued",
            "status_message": "Queued VM creation",
            "progress": 0,
            "transitioning": True,
            "next_poll_seconds": 2,
            "error": None,
            "created_at": "2026-05-14T12:00:00+00:00",
            "updated_at": "2026-05-14T12:00:01+00:00",
        }

    async def active_recent_jobs(self):
        return [await self.get_job("job-a")]


def test_requestor_vm_endpoint_rejects_missing_token():
    response = TestClient(app).get("/api/v1/vms/vm-a")

    assert response.status_code == 401


@pytest.mark.parametrize("path", VM_READ_ENDPOINTS)
def test_vm_read_endpoints_reject_missing_requestor_token(path: str):
    response = TestClient(app).get(path)

    assert response.status_code == 401


@pytest.mark.parametrize("path", VM_READ_ENDPOINTS)
def test_vm_read_endpoints_reject_wrong_owner(path: str):
    token = _requestor_token("vm-a", REQUESTOR_KEY)
    _override_auth(owner=OTHER)
    try:
        response = TestClient(app).get(path, headers=_requestor_headers(token))
    finally:
        app.container.provider_auth_service.reset_override()

    assert response.status_code == 403


def test_vm_job_endpoint_rejects_wrong_owner():
    token = _requestor_token("vm-a", OTHER_KEY)
    _override_auth(owner=REQUESTOR)
    try:
        response = TestClient(app).get(
            "/api/v1/vms/jobs/job-a", headers=_requestor_headers(token)
        )
    finally:
        app.container.provider_auth_service.reset_override()

    assert response.status_code == 403


@pytest.mark.parametrize(("method", "path", "payload"), VM_WRITE_ENDPOINTS)
def test_vm_write_endpoints_reject_missing_requestor_token(
    method: str, path: str, payload: dict | None
):
    response = TestClient(app).request(method, path, json=payload)

    assert response.status_code == 401


@pytest.mark.parametrize(("method", "path", "payload"), VM_WRITE_ENDPOINTS)
def test_vm_write_endpoints_reject_wrong_owner(
    method: str, path: str, payload: dict | None
):
    token = _requestor_token("vm-a", REQUESTOR_KEY)
    _override_auth(owner=OTHER)
    try:
        response = TestClient(app).request(
            method, path, headers=_requestor_headers(token), json=payload
        )
    finally:
        app.container.provider_auth_service.reset_override()

    assert response.status_code == 403


def test_requestor_vm_endpoint_rejects_malformed_token():
    _override_auth(owner=REQUESTOR)
    try:
        response = TestClient(app).get(
            "/api/v1/vms/vm-a", headers={"authorization": "Bearer not-a-jwt"}
        )
    finally:
        app.container.provider_auth_service.reset_override()

    assert response.status_code == 401


def test_requestor_vm_endpoint_rejects_wrong_vm_token():
    token = _requestor_token("vm-b", REQUESTOR_KEY)
    _override_auth(owner=REQUESTOR)
    try:
        response = TestClient(app).get(
            "/api/v1/vms/vm-a", headers=_requestor_headers(token)
        )
    finally:
        app.container.provider_auth_service.reset_override()

    assert response.status_code == 403


def test_requestor_vm_endpoint_rejects_wrong_owner():
    token = _requestor_token("vm-a", REQUESTOR_KEY)
    _override_auth(owner=OTHER)
    try:
        response = TestClient(app).get(
            "/api/v1/vms/vm-a", headers=_requestor_headers(token)
        )
    finally:
        app.container.provider_auth_service.reset_override()

    assert response.status_code == 403


def test_requestor_vm_endpoint_accepts_owner_token():
    token = _requestor_token("vm-a", REQUESTOR_KEY)
    vm_info = VMInfo(
        id="vm-a",
        name="vm-a",
        status=VMStatus.RUNNING,
        resources=VMResources(cpu=1, memory=1, storage=10),
    )
    _override_auth(owner=REQUESTOR)
    app.container.vm_service().get_vm_status = AsyncMock(return_value=vm_info)
    try:
        response = TestClient(app).get(
            "/api/v1/vms/vm-a", headers=_requestor_headers(token)
        )
    finally:
        app.container.provider_auth_service.reset_override()

    assert response.status_code == 200
    assert response.json()["id"] == "vm-a"


@pytest.mark.asyncio
async def test_provider_auth_resolves_owner_from_create_job_before_stream_mapping():
    service = ProviderAuthService(
        settings={
            "PROVIDER_ID": PROVIDER,
            "VM_DATA_DIR": "/tmp",
            "REQUESTOR_SESSION_SECRET": "test-secret",
            "PROVIDER_ADMIN_TOKEN": "admin-token",
        },
        stream_map=FakeStreamMap(owner=None, stream_id=None),
        job_store=FakeJobStore(),
        reader_factory=lambda: None,
    )

    owner = await service.resolve_vm_owner("vm-a")

    assert owner == REQUESTOR


def test_requestor_vm_endpoint_accepts_admin_token_for_provider_owner():
    vm_info = VMInfo(
        id="vm-a",
        name="vm-a",
        status=VMStatus.RUNNING,
        resources=VMResources(cpu=1, memory=1, storage=10),
    )
    _override_auth(owner=REQUESTOR)
    app.container.vm_service().get_vm_status = AsyncMock(return_value=vm_info)
    try:
        response = TestClient(app).get(
            "/api/v1/vms/vm-a", headers={"authorization": "Bearer admin-token"}
        )
    finally:
        app.container.provider_auth_service.reset_override()

    assert response.status_code == 200
    assert response.json()["id"] == "vm-a"


def test_admin_endpoint_rejects_requestor_token():
    token = _requestor_token("vm-a", REQUESTOR_KEY)
    _override_auth(owner=REQUESTOR)
    try:
        response = TestClient(app).get("/api/v1/vms", headers=_requestor_headers(token))
    finally:
        app.container.provider_auth_service.reset_override()

    assert response.status_code == 401


def test_admin_endpoint_rejects_missing_admin_token():
    response = TestClient(app).get("/api/v1/vms")

    assert response.status_code == 401


def test_admin_endpoint_accepts_admin_token():
    _override_auth(owner=REQUESTOR)
    app.container.vm_service().list_vms = AsyncMock(return_value=[])
    try:
        response = TestClient(app).get(
            "/api/v1/vms", headers={"authorization": "Bearer admin-token"}
        )
    finally:
        app.container.provider_auth_service.reset_override()

    assert response.status_code == 200


def test_create_vm_rejects_free_requestor_vm():
    token = _requestor_token("vm-a", REQUESTOR_KEY)
    _override_auth(owner=REQUESTOR)
    try:
        response = TestClient(app).post(
            "/api/v1/vms",
            headers=_requestor_headers(token),
            json={
                "name": "vm-a",
                "ssh_key": "ssh-rsa AAA...",
                "resources": {"cpu": 1, "memory": 1, "storage": 10},
            },
        )
    finally:
        app.container.provider_auth_service.reset_override()

    assert response.status_code == 400
    assert "payment" in response.json()["detail"]


def test_requestor_session_rejects_expired_signature():
    command = _session_command("vm-a", REQUESTOR_KEY, deadline=int(time.time()) - 1)
    _override_auth(owner=REQUESTOR)
    try:
        response = TestClient(app).post("/api/v1/auth/requestor-sessions", json=command)
    finally:
        app.container.provider_auth_service.reset_override()

    assert response.status_code == 401


def test_requestor_session_rejects_replayed_nonce():
    command = _session_command("vm-a", REQUESTOR_KEY)
    _override_auth(owner=REQUESTOR)
    try:
        client = TestClient(app)
        first = client.post("/api/v1/auth/requestor-sessions", json=command)
        second = client.post("/api/v1/auth/requestor-sessions", json=command)
    finally:
        app.container.provider_auth_service.reset_override()

    assert first.status_code == 200
    assert second.status_code == 401


def test_requestor_session_rejects_wrong_provider_signature():
    command = _session_command(
        "vm-a",
        REQUESTOR_KEY,
        signed_provider="0x5555555555555555555555555555555555555555",
    )
    _override_auth(owner=REQUESTOR)
    try:
        response = TestClient(app).post("/api/v1/auth/requestor-sessions", json=command)
    finally:
        app.container.provider_auth_service.reset_override()

    assert response.status_code == 401


def test_requestor_session_rejects_wrong_wallet_signature():
    command = _session_command("vm-a", REQUESTOR_KEY)
    command["signature"] = _sign_session(command, OTHER_KEY)
    _override_auth(owner=REQUESTOR)
    try:
        response = TestClient(app).post("/api/v1/auth/requestor-sessions", json=command)
    finally:
        app.container.provider_auth_service.reset_override()

    assert response.status_code == 401


def _override_auth(owner: str):
    settings = {
        "PROVIDER_ID": PROVIDER,
        "VM_DATA_DIR": "/tmp",
        "REQUESTOR_SESSION_SECRET": "test-secret",
        "PROVIDER_ADMIN_TOKEN": "admin-token",
    }
    service = ProviderAuthService(
        settings=settings,
        stream_map=FakeStreamMap(owner),
        job_store=FakeJobStore(),
        reader_factory=lambda: None,
    )
    app.container.provider_auth_service.override(service)


def _requestor_token(vm_id: str, private_key: str) -> str:
    _override_auth(owner=REQUESTOR)
    try:
        command = _session_command(vm_id, private_key)
        response = TestClient(app).post("/api/v1/auth/requestor-sessions", json=command)
        assert response.status_code == 200
        return response.json()["access_token"]
    finally:
        app.container.provider_auth_service.reset_override()


def _session_command(
    vm_id: str,
    private_key: str,
    *,
    deadline: int | None = None,
    signed_provider: str = PROVIDER,
) -> dict:
    command = {
        "requestor_address": Account.from_key(private_key).address,
        "vm_id": vm_id,
        "scope": "vm",
        "nonce": f"nonce-{time.time_ns()}",
        "deadline": deadline or int(time.time()) + 300,
    }
    command["signature"] = _sign_session(
        command, private_key, signed_provider=signed_provider
    )
    return command


def _sign_session(
    command: dict, private_key: str, *, signed_provider: str = PROVIDER
) -> str:
    signable = encode_typed_data(
        domain_data={
            "name": REQUESTOR_SESSION_DOMAIN,
            "version": REQUESTOR_SESSION_VERSION,
        },
        message_types={
            "ProviderSession": [
                {"name": "provider", "type": "address"},
                {"name": "requestor", "type": "address"},
                {"name": "vmId", "type": "string"},
                {"name": "scope", "type": "string"},
                {"name": "nonce", "type": "string"},
                {"name": "deadline", "type": "uint256"},
            ]
        },
        message_data={
            "provider": signed_provider,
            "requestor": command["requestor_address"],
            "vmId": command["vm_id"],
            "scope": command["scope"],
            "nonce": command["nonce"],
            "deadline": command["deadline"],
        },
    )
    return Account.sign_message(signable, private_key=private_key).signature.hex()


def _requestor_headers(token: str):
    return {"authorization": f"Bearer {token}"}
