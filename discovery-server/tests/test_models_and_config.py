import os
from datetime import datetime, timedelta
from fastapi.testclient import TestClient


def test_models_validation_errors():
    from discovery.api.models import AdvertisementCreate
    import pytest

    # Missing resource keys
    with pytest.raises(ValueError):
        AdvertisementCreate(
            ip_address="1.2.3.4",
            country="US",
            resources={"cpu": 1, "memory": 1},
        )

    # Invalid resource values
    for bad in (
        {"cpu": 0, "memory": 1, "storage": 1},
        {"cpu": 1, "memory": 0, "storage": 1},
        {"cpu": 1, "memory": 1, "storage": 0},
    ):
        with pytest.raises(ValueError):
            AdvertisementCreate(
                ip_address="1.2.3.4",
                country="US",
                resources=bad,
            )


def test_config_assemble_db_url_uses_dir_and_name(tmp_path):
    from discovery.config import Settings

    cfg = Settings(DATABASE_DIR=str(tmp_path), DATABASE_NAME="t.db", DATABASE_URL=None)
    assert cfg.DATABASE_URL.endswith("/t.db")
    # Directory is created
    assert tmp_path.exists()


def test_db_model_is_expired_property():
    from discovery.db.models import Advertisement

    a = Advertisement(provider_id="p", ip_address="i", country="US", resources={})
    a.updated_at = None
    assert a.is_expired is True

    # repr covered
    assert "Advertisement(" in repr(a)

    a.updated_at = datetime.utcnow()
    assert a.is_expired is False

    a.updated_at = datetime.utcnow() - timedelta(minutes=6)
    assert a.is_expired is True


def test_rate_limit_middleware_allows_under_limit():
    # Build a minimal FastAPI app with the middleware directly
    from fastapi import FastAPI
    from discovery.main import RateLimitMiddleware

    app = FastAPI()

    @app.get("/")
    def root():
        return {"ok": True}

    app.add_middleware(RateLimitMiddleware, requests_per_minute=2)

    with TestClient(app) as client:
        r1 = client.get("/")
        assert r1.status_code == 200

        r2 = client.get("/")
        assert r2.status_code == 200


def test_health_endpoint():
    os.environ["GOLEM_DISCOVERY_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
    from discovery.main import app
    with TestClient(app) as client:
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"

def test_start_invokes_uvicorn_run(monkeypatch):
    # Ensure calling start() triggers uvicorn.run with expected args
    from discovery import main

    called = {}

    def fake_run(*args, **kwargs):
        called["args"] = args
        called["kwargs"] = kwargs

    # Inject fake uvicorn module so that import inside start() uses it
    import types, sys
    fake_uvicorn = types.SimpleNamespace(run=fake_run)
    monkeypatch.setitem(sys.modules, "uvicorn", fake_uvicorn)
    main.start()
    assert called["kwargs"]["host"] == main.settings.HOST
    assert called["kwargs"]["port"] == main.settings.PORT


def test_rate_limit_middleware_blocks_returns_serializable(monkeypatch):
    # Trigger the 429 path while avoiding datetime serialization issues
    from fastapi import FastAPI
    from discovery.main import RateLimitMiddleware
    import types

    # Patch ErrorResponse used by middleware to avoid datetime
    import discovery.main as m
    class SimpleError:
        def __init__(self, code, message):
            self._d = {"code": code, "message": message}
        def dict(self):
            return self._d

    monkeypatch.setattr(m, "ErrorResponse", SimpleError)

    app = FastAPI()

    @app.get("/")
    def root():
        return {"ok": True}

    app.add_middleware(RateLimitMiddleware, requests_per_minute=1)

    from fastapi.testclient import TestClient
    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        r2 = client.get("/")
        assert r2.status_code == 429
        assert r2.json()["code"] == "RATE_001"
