from pathlib import Path

import httpx
import pytest

from provider.cli.admin_client import (
    ProviderAdminClient,
    ProviderCliError,
    provider_admin_env,
)


def test_admin_client_sends_bearer_token(monkeypatch):
    captured = {}

    class FakeClient:
        def __init__(self, timeout):
            captured["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def request(self, method, url, headers=None, json=None, params=None):
            captured.update(
                {
                    "method": method,
                    "url": url,
                    "headers": headers,
                    "json": json,
                    "params": params,
                }
            )
            return httpx.Response(200, json={"ok": True})

    monkeypatch.setattr(httpx, "Client", FakeClient)

    result = ProviderAdminClient(
        base_url="http://localhost:7466/api/v1", token="secret"
    ).get("/provider/settings", params={"a": "b"})

    assert result == {"ok": True}
    assert captured["method"] == "GET"
    assert captured["url"] == "http://localhost:7466/api/v1/provider/settings"
    assert captured["headers"]["Authorization"] == "Bearer secret"
    assert captured["params"] == {"a": "b"}


def test_admin_client_reports_rejected_token(monkeypatch):
    class FakeClient:
        def __init__(self, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def request(self, method, url, headers=None, json=None, params=None):
            return httpx.Response(401, json={"detail": "nope"})

    monkeypatch.setattr(httpx, "Client", FakeClient)

    with pytest.raises(ProviderCliError, match="admin token was rejected"):
        ProviderAdminClient(token="bad").get("/provider/settings")


def test_provider_admin_env_matches_headless_runtime(monkeypatch, tmp_path):
    monkeypatch.setenv("GOLEM_PROVIDER_VM_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("GOLEM_PROVIDER_ADMIN_TOKEN", raising=False)

    env = provider_admin_env()

    assert env["GOLEM_PROVIDER_VM_DATA_DIR"] == str(tmp_path)
    assert env["GOLEM_PROVIDER_DISABLE_RELOAD"] == "1"
    assert env["GOLEM_PROVIDER_ADMIN_TOKEN"]
    assert (Path(tmp_path) / "provider-admin.token").exists()
