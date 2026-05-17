import pytest
from fastapi.testclient import TestClient


def test_advertisement_payload_validation_errors():
    from central_discovery.domain import AdvertisementPayload

    with pytest.raises(ValueError):
        AdvertisementPayload(
            ip_address="1.2.3.4",
            country="US",
            resources={"cpu": 1, "memory": 1},
        )

    for bad in (
        {"cpu": 0, "memory": 1, "storage": 1},
        {"cpu": 1, "memory": 0, "storage": 1},
        {"cpu": 1, "memory": 1, "storage": 0},
    ):
        with pytest.raises(ValueError):
            AdvertisementPayload(
                ip_address="1.2.3.4",
                country="US",
                resources=bad,
            )


def test_central_config_uses_only_canonical_prefix(monkeypatch):
    from central_discovery.config import Settings

    monkeypatch.setenv("UNRELATED_DISCOVERY_PORT", "7777")
    monkeypatch.delenv("GOLEM_CENTRAL_DISCOVERY_PORT", raising=False)

    assert Settings().PORT == 9001

    monkeypatch.setenv("GOLEM_CENTRAL_DISCOVERY_PORT", "7777")
    assert Settings().PORT == 7777


def test_rate_limit_middleware_allows_under_limit():
    from fastapi import FastAPI

    from central_discovery.main import RateLimitMiddleware

    app = FastAPI()

    @app.get("/")
    def root():
        return {"ok": True}

    app.add_middleware(RateLimitMiddleware, requests_per_minute=2)

    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        assert client.get("/").status_code == 200
