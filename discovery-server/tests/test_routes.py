import os
import pytest
from fastapi.testclient import TestClient
from fastapi import Depends


@pytest.fixture(scope="module")
def app_client():
    os.environ["GOLEM_DISCOVERY_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
    from discovery.main import app
    with TestClient(app) as client:
        yield client


def _headers(pid: str = "prov1"):
    return {"X-Provider-ID": pid, "X-Provider-Signature": "sig"}


def test_missing_provider_headers_returns_401(app_client: TestClient):
    body = {
        "ip_address": "1.2.3.4",
        "country": "US",
        "resources": {"cpu": 1, "memory": 1, "storage": 1},
    }
    # Pass empty headers to hit our explicit 401 branch in dependency
    headers = {"X-Provider-ID": "", "X-Provider-Signature": ""}
    r = app_client.post("/api/v1/advertisements", json=body, headers=headers)
    assert r.status_code == 401
    assert r.json()["detail"]["code"] == "AUTH_003"


def test_get_not_found_returns_404(app_client: TestClient):
    r = app_client.get("/api/v1/advertisements/does-not-exist")
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "ADV_004"


def test_list_invalid_requirements_returns_400(app_client: TestClient):
    r = app_client.get("/api/v1/advertisements?cpu=0")
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "ADV_002"


def test_create_list_get_delete_flow_and_filters(app_client: TestClient):
    # Create two advertisements
    a1 = {
        "ip_address": "1.1.1.1",
        "country": "US",
        "resources": {"cpu": 2, "memory": 4, "storage": 50},
    }
    a2 = {
        "ip_address": "2.2.2.2",
        "country": "SE",
        "resources": {"cpu": 4, "memory": 8, "storage": 100},
    }
    r1 = app_client.post("/api/v1/advertisements", json=a1, headers=_headers("provA"))
    r2 = app_client.post("/api/v1/advertisements", json=a2, headers=_headers("provB"))
    assert r1.status_code == 200 and r2.status_code == 200

    # List with filters - by CPU
    r = app_client.get("/api/v1/advertisements?cpu=3")
    assert r.status_code == 200
    providers = {item["provider_id"] for item in r.json()}
    assert providers == {"provB"}

    # List with country filter
    r = app_client.get("/api/v1/advertisements?country=US")
    providers = {item["provider_id"] for item in r.json()}
    assert providers == {"provA"}

    # List with memory filter
    r = app_client.get("/api/v1/advertisements?memory=6")
    providers = {item["provider_id"] for item in r.json()}
    assert providers == {"provB"}

    # List with storage filter
    r = app_client.get("/api/v1/advertisements?storage=60")
    providers = {item["provider_id"] for item in r.json()}
    assert providers == {"provB"}

    # Get specific
    r = app_client.get("/api/v1/advertisements/provB")
    assert r.status_code == 200
    assert r.json()["ip_address"] == "2.2.2.2"

    # Delete unauthorized (header mismatch)
    r = app_client.delete("/api/v1/advertisements/provA", headers=_headers("other"))
    assert r.status_code == 401
    assert r.json()["detail"]["code"] == "AUTH_004"

    # Delete not found
    r = app_client.delete("/api/v1/advertisements/nope", headers=_headers("nope"))
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "ADV_004"

    # Delete success
    r = app_client.delete("/api/v1/advertisements/provA", headers=_headers("provA"))
    assert r.status_code == 200
    assert r.json()["status"] == "success"

    # Confirm deleted
    r = app_client.get("/api/v1/advertisements/provA")
    assert r.status_code == 404


def test_create_route_handles_repo_exception(monkeypatch):
    os.environ["GOLEM_DISCOVERY_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
    from discovery.main import app
    from discovery.api import routes

    class BoomRepo:
        async def upsert_advertisement(self, **kwargs):
            raise RuntimeError("boom")

    def override_repo():
        return BoomRepo()

    app.dependency_overrides[routes.get_repository] = override_repo
    with TestClient(app) as client:
        r = client.post(
            "/api/v1/advertisements",
            json={
                "ip_address": "3.3.3.3",
                "country": "US",
                "resources": {"cpu": 1, "memory": 1, "storage": 1},
            },
            headers=_headers("provX"),
        )
        assert r.status_code == 400
        assert r.json()["detail"]["code"] == "ADV_001"
    app.dependency_overrides.clear()


def test_list_route_handles_repo_exception(monkeypatch):
    os.environ["GOLEM_DISCOVERY_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
    from discovery.main import app
    from discovery.api import routes

    class BoomRepo:
        async def find_by_requirements(self, **kwargs):
            raise RuntimeError("boom")

    def override_repo():
        return BoomRepo()

    app.dependency_overrides[routes.get_repository] = override_repo
    with TestClient(app) as client:
        r = client.get("/api/v1/advertisements")
        assert r.status_code == 400
        assert r.json()["detail"]["code"] == "ADV_003"
    app.dependency_overrides.clear()
