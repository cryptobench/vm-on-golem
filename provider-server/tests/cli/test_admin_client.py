import httpx
import pytest

from provider.cli.admin_client import ProviderAdminClient, ProviderCliError


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
