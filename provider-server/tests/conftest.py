import os

import pytest

# Ensure provider config bootstrap is skipped in tests to avoid filesystem writes
os.environ.setdefault("GOLEM_PROVIDER_SKIP_BOOTSTRAP", "1")

# Provide a dummy private key to avoid EthereumIdentity file I/O
os.environ.setdefault(
    "GOLEM_PROVIDER_ETHEREUM_PRIVATE_KEY",
    "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
)

# Avoid auto-detecting multipass binary during settings load
os.environ.setdefault("GOLEM_PROVIDER_MULTIPASS_BINARY_PATH", "/bin/echo")

# Make retries/timeouts fast in tests to avoid long waits
os.environ.setdefault("GOLEM_PROVIDER_RETRY_ATTEMPTS", "1")
os.environ.setdefault("GOLEM_PROVIDER_RETRY_DELAY_SECONDS", "0.05")
os.environ.setdefault("GOLEM_PROVIDER_RETRY_BACKOFF", "1.0")
os.environ.setdefault("GOLEM_PROVIDER_CREATE_VM_MAX_RETRIES", "2")
os.environ.setdefault("GOLEM_PROVIDER_CREATE_VM_RETRY_DELAY_SECONDS", "0.05")
os.environ.setdefault("GOLEM_PROVIDER_LAUNCH_TIMEOUT_SECONDS", "5")


@pytest.fixture(autouse=True)
def _legacy_provider_api_auth_overrides(request):
    if "tests/api/test_provider_auth.py" in request.node.nodeid:
        yield
        return

    from fastapi import Request

    from provider.auth.dependencies import (
        require_provider_admin,
        require_requestor_vm_access,
    )
    from provider.auth.domain import AdminIdentity, RequestorIdentity
    from provider.main import app

    async def _requestor_identity(req: Request):
        vm_id = req.path_params.get("requestor_name")
        if vm_id is None and req.method == "POST" and req.url.path.endswith("/vms"):
            try:
                vm_id = (await req.json()).get("name")
            except Exception:
                vm_id = None
        return RequestorIdentity(
            requestor_address="0x3333333333333333333333333333333333333333",
            vm_id=vm_id or "test-vm",
            token_id="legacy-test",
            expires_at=9999999999,
        )

    async def _admin_identity():
        return AdminIdentity()

    app.dependency_overrides[require_requestor_vm_access] = _requestor_identity
    app.dependency_overrides[require_provider_admin] = _admin_identity
    try:
        yield
    finally:
        app.dependency_overrides.pop(require_requestor_vm_access, None)
        app.dependency_overrides.pop(require_provider_admin, None)
