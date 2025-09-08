import os
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def app_client():
    # Use in-memory SQLite for tests and ensure startup events run
    os.environ["GOLEM_DISCOVERY_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
    from discovery.main import app
    with TestClient(app) as client:
        yield client


def test_create_and_get_advertisement_with_pricing(app_client: TestClient):
    headers = {
        "X-Provider-ID": "0xabc",
        "X-Provider-Signature": "sig",
    }
    body = {
        "ip_address": "1.2.3.4",
        "country": "SE",
        "resources": {"cpu": 2, "memory": 2, "storage": 10},
        "pricing": {
            "usd_per_core_month": 6.0,
            "usd_per_gb_ram_month": 2.5,
            "usd_per_gb_storage_month": 0.12,
            "glm_per_core_month": 12.0,
            "glm_per_gb_ram_month": 5.0,
            "glm_per_gb_storage_month": 0.24,
        },
    }
    r = app_client.post("/api/v1/advertisements", json=body, headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["provider_id"] == "0xabc"
    assert data["pricing"]["usd_per_core_month"] == 6.0

    r2 = app_client.get("/api/v1/advertisements/0xabc")
    assert r2.status_code == 200
    assert r2.json()["pricing"]["glm_per_gb_ram_month"] == 5.0
