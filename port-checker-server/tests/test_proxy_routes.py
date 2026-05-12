import asyncio
import json
import types
from typing import Any

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from port_checker.app import create_app
from port_checker.config import Settings
from port_checker.proxy import api as proxy_api
from port_checker.proxy import arkiv_resolver, central_resolver, forwarder


class _StubResp:
    def __init__(
        self,
        status: int,
        headers: dict[str, str] | None = None,
        body: bytes | None = None,
        json_obj: Any | None = None,
    ):
        self.status = status
        self.headers = headers or {}
        self._body = body or b""
        self._json = json_obj

    async def read(self):
        return self._body

    async def json(self):
        if self._json is not None:
            return self._json
        return json.loads(self._body.decode() or "{}")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _StubSession:
    client_error_cls = Exception

    def __init__(self, routes):
        self.routes = routes
        self.last = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def _handle(self, method: str, url: str, **kwargs):
        key = (method.upper(), url)
        if key not in self.routes:
            raise AssertionError(f"No stub for {key}")
        self.last[key] = kwargs
        value = self.routes[key]
        if isinstance(value, dict) and value.get("raise") == "timeout":
            raise asyncio.TimeoutError()
        if isinstance(value, dict) and value.get("raise") == "client":
            raise self.client_error_cls("boom")
        return value

    def get(self, url: str, **kwargs):
        return self._handle("GET", url, **kwargs)

    def request(self, method: str, url: str, **kwargs):
        return self._handle(method, url, **kwargs)


def _patch_aiohttp(monkeypatch, session):
    class _ClientError(Exception):
        pass

    _StubSession.client_error_cls = _ClientError
    aiohttp_stub = types.SimpleNamespace(
        ClientSession=lambda timeout=None: session,
        ClientTimeout=lambda **kwargs: object(),
        ClientError=_ClientError,
    )
    monkeypatch.setattr(central_resolver, "aiohttp", aiohttp_stub)
    monkeypatch.setattr(forwarder, "aiohttp", aiohttp_stub)


def _client(settings: Settings | None = None) -> TestClient:
    return TestClient(
        create_app(settings or Settings(PORT_CHECKER_PROXY_TOKEN="secret"))
    )


def test_health_and_direct_disabled():
    client = _client(
        Settings(
            PORT_CHECKER_PROXY_ENABLED=True,
            PORT_CHECKER_PROXY_ALLOW_DIRECT_IP=False,
            PORT_CHECKER_PROXY_TOKEN="secret",
        )
    )

    assert client.get("/health").json() == {"status": "ok"}
    response = client.get(
        "/proxy/status",
        headers={"X-Forward-To": "1.1.1.1:80", "X-Proxy-Token": "secret"},
    )
    assert response.status_code == 404


def test_provider_proxy_central_success(monkeypatch):
    advertisement_url = "http://localhost:9001/api/v1/advertisements/prov123"
    upstream_url = "http://1.1.1.1:8080/status?foo=bar"
    session = _StubSession(
        {
            ("GET", advertisement_url): _StubResp(
                200, json_obj={"ip_address": "1.1.1.1"}
            ),
            ("GET", upstream_url): _StubResp(
                200,
                headers={"Server": "prov", "Connection": "keep-alive"},
                body=b"OK",
            ),
        }
    )
    _patch_aiohttp(monkeypatch, session)
    client = _client(Settings(PORT_CHECKER_PROXY_TOKEN="secret"))

    response = client.get(
        "/proxy/provider/prov123/status?port=8080&foo=bar",
        headers={"X-Proxy-Token": "secret", "X-Proxy-Source": "central"},
    )

    assert response.status_code == 200
    assert response.content == b"OK"
    assert response.headers["Server"] == "prov"
    assert response.headers["X-Proxy"] == "golem-port-checker"
    assert response.headers["X-Proxy-Provider-Id"] == "prov123"
    assert "Connection" not in response.headers
    sent_headers = session.last[("GET", upstream_url)]["headers"]
    assert "X-Proxy-Token" not in sent_headers
    assert "X-Proxy-Source" not in sent_headers
    assert "X-Real-IP" in sent_headers


def test_provider_websocket_proxy_central_success(monkeypatch):
    advertisement_url = "http://localhost:9001/api/v1/advertisements/prov123"
    session = _StubSession(
        {("GET", advertisement_url): _StubResp(200, json_obj={"ip_address": "1.1.1.1"})}
    )
    _patch_aiohttp(monkeypatch, session)
    captured = {}

    class _Forwarder:
        def __init__(self, settings):
            self.settings = settings

        async def forward(self, *, websocket, url, headers):
            captured.update({"url": url, "headers": headers})
            await websocket.accept()
            await websocket.send_json({"ok": True})
            await websocket.close()

    monkeypatch.setattr(proxy_api, "WebSocketForwarder", _Forwarder)
    client = _client(Settings(PORT_CHECKER_PROXY_TOKEN="secret"))

    with client.websocket_connect(
        "/proxy/provider/prov123/api/v1/vms/vm-a/live"
        "?port=8080&proxy_token=secret&proxy_source=central&history_range=1h"
    ) as websocket:
        assert websocket.receive_json() == {"ok": True}

    assert captured["url"] == "ws://1.1.1.1:8080/api/v1/vms/vm-a/live?history_range=1h"
    assert "sec-websocket-key" not in {key.lower() for key in captured["headers"]}


def test_provider_websocket_proxy_missing_token_rejected():
    client = _client(Settings(PORT_CHECKER_PROXY_TOKEN="secret"))

    try:
        with client.websocket_connect("/proxy/provider/prov/status?port=80"):
            raise AssertionError("websocket unexpectedly connected")
    except WebSocketDisconnect as exc:
        assert exc.code == 1008


def test_provider_proxy_arkiv_success(monkeypatch):
    upstream_url = "http://3.4.5.6:8080/status?foo=bar"
    session = _StubSession(
        {("GET", upstream_url): _StubResp(200, headers={"Server": "prov"}, body=b"OK")}
    )
    _patch_aiohttp(monkeypatch, session)

    created = {}

    class _ArkivClient:
        async def query_entities(self, query: str):
            assert "golem_provider_id" in query
            return [types.SimpleNamespace(entity_key="0x" + ("00" * 32))]

        async def get_entity_metadata(self, entity_key):
            return types.SimpleNamespace(
                string_annotations=[
                    types.SimpleNamespace(key="golem_ip_address", value="3.4.5.6")
                ]
            )

        async def disconnect(self):
            return None

    async def create_arkiv_client(rpc_url: str, ws_url: str):
        created.update({"rpc_url": rpc_url, "ws_url": ws_url})
        return _ArkivClient()

    monkeypatch.setattr(arkiv_resolver, "_create_arkiv_client", create_arkiv_client)
    monkeypatch.setattr(arkiv_resolver, "_entity_key_from_hex", lambda value: value)

    client = _client(
        Settings(
            PORT_CHECKER_PROXY_TOKEN="secret",
            ARKIV_RPC_URL="http://rpc.default",
            ARKIV_WS_URL="ws://ws.default",
        )
    )

    response = client.get(
        "/proxy/provider/prov123/status?port=8080&foo=bar",
        headers={
            "X-Proxy-Token": "secret",
            "X-Proxy-Source": "arkiv",
            "X-Proxy-Arkiv-Rpc": "http://rpc.override",
            "X-Proxy-Arkiv-Ws": "ws://ws.override",
        },
    )

    assert response.status_code == 200
    assert response.content == b"OK"
    assert created == {"rpc_url": "http://rpc.override", "ws_url": "ws://ws.override"}


def test_provider_proxy_rejects_unknown_source():
    client = _client(Settings(PORT_CHECKER_PROXY_TOKEN="secret"))

    response = client.get(
        "/proxy/provider/prov/status?port=80",
        headers={"X-Proxy-Token": "secret", "X-Proxy-Source": "legacy"},
    )

    assert response.status_code == 400


def test_provider_proxy_missing_token():
    client = _client(Settings(PORT_CHECKER_PROXY_TOKEN="secret"))

    response = client.get("/proxy/provider/prov/status")

    assert response.status_code == 403


def test_provider_proxy_disallowed_port():
    client = _client(
        Settings(
            PORT_CHECKER_PROXY_TOKEN="secret",
            PORT_CHECKER_PROXY_ALLOWED_PORTS="80,443",
        )
    )

    response = client.get(
        "/proxy/provider/prov/status?port=8080",
        headers={"X-Proxy-Token": "secret", "X-Proxy-Source": "central"},
    )

    assert response.status_code == 403


def test_provider_proxy_body_too_large():
    client = _client(
        Settings(
            PORT_CHECKER_PROXY_TOKEN="secret",
            PORT_CHECKER_PROXY_MAX_BODY_BYTES=10,
        )
    )

    response = client.post(
        "/proxy/provider/pid/upload?port=80",
        headers={"X-Proxy-Token": "secret", "X-Proxy-Source": "central"},
        data=b"01234567890",
    )

    assert response.status_code == 413


def test_provider_proxy_central_timeout_and_client_error(monkeypatch):
    timeout_session = _StubSession(
        {
            ("GET", "http://localhost:9001/api/v1/advertisements/slow"): {
                "raise": "timeout"
            }
        }
    )
    _patch_aiohttp(monkeypatch, timeout_session)
    client = _client(Settings(PORT_CHECKER_PROXY_TOKEN="secret"))

    response = client.get(
        "/proxy/provider/slow/status?port=80",
        headers={"X-Proxy-Token": "secret", "X-Proxy-Source": "central"},
    )
    assert response.status_code == 504

    client_error_session = _StubSession(
        {
            ("GET", "http://localhost:9001/api/v1/advertisements/fail"): {
                "raise": "client"
            }
        }
    )
    _patch_aiohttp(monkeypatch, client_error_session)
    response = client.get(
        "/proxy/provider/fail/status?port=80",
        headers={"X-Proxy-Token": "secret", "X-Proxy-Source": "central"},
    )
    assert response.status_code == 502


def test_provider_proxy_upstream_timeout(monkeypatch):
    session = _StubSession(
        {
            ("GET", "http://localhost:9001/api/v1/advertisements/prov"): _StubResp(
                200, json_obj={"ip_address": "1.2.3.4"}
            ),
            ("GET", "http://1.2.3.4:80/slow"): {"raise": "timeout"},
        }
    )
    _patch_aiohttp(monkeypatch, session)
    client = _client(Settings(PORT_CHECKER_PROXY_TOKEN="secret"))

    response = client.get(
        "/proxy/provider/prov/slow?port=80",
        headers={"X-Proxy-Token": "secret", "X-Proxy-Source": "central"},
    )

    assert response.status_code == 504


def test_provider_proxy_arkiv_missing_urls():
    client = _client(Settings(PORT_CHECKER_PROXY_TOKEN="secret"))

    response = client.get(
        "/proxy/provider/prov/status?port=80",
        headers={"X-Proxy-Token": "secret", "X-Proxy-Source": "arkiv"},
    )

    assert response.status_code == 500


def test_direct_ip_enabled_with_token(monkeypatch):
    session = _StubSession(
        {
            ("GET", "http://2.2.2.2:8000/info?foo=bar"): _StubResp(
                200,
                headers={"Server": "prov", "Connection": "keep-alive"},
                body=b"DIRECT",
            )
        }
    )
    _patch_aiohttp(monkeypatch, session)
    client = _client(
        Settings(
            PORT_CHECKER_PROXY_TOKEN="secret",
            PORT_CHECKER_PROXY_ALLOW_DIRECT_IP=True,
        )
    )

    response = client.get(
        "/proxy/info?foo=bar&target=shouldremove",
        headers={"X-Forward-To": "2.2.2.2:8000", "X-Proxy-Token": "secret"},
    )

    assert response.status_code == 200
    assert response.content == b"DIRECT"
    assert "Connection" not in response.headers


def test_direct_ip_validation_paths():
    client = _client(
        Settings(
            PORT_CHECKER_PROXY_TOKEN="secret",
            PORT_CHECKER_PROXY_ALLOW_DIRECT_IP=True,
            PORT_CHECKER_PROXY_ALLOWED_PORTS="80",
        )
    )

    assert (
        client.get("/proxy/info", headers={"X-Proxy-Token": "secret"}).status_code
        == 400
    )
    assert (
        client.get(
            "/proxy/info",
            headers={"X-Proxy-Token": "secret", "X-Forward-To": "1.1.1.1:abc"},
        ).status_code
        == 400
    )
    assert (
        client.get(
            "/proxy/info",
            headers={"X-Proxy-Token": "secret", "X-Forward-To": "127.0.0.1:80"},
        ).status_code
        == 400
    )
    assert (
        client.get(
            "/proxy/info",
            headers={"X-Proxy-Token": "secret", "X-Forward-To": "1.1.1.1:81"},
        ).status_code
        == 403
    )
    assert (
        client.get(
            "/proxy/info",
            headers={
                "X-Proxy-Token": "secret",
                "X-Forward-To": "1.1.1.1:80",
                "X-Forward-Protocol": "https",
            },
        ).status_code
        == 400
    )


def test_proxy_disabled_for_both_routes():
    client = _client(
        Settings(PORT_CHECKER_PROXY_ENABLED=False, PORT_CHECKER_PROXY_TOKEN="secret")
    )

    provider_response = client.get(
        "/proxy/provider/prov/status?port=80",
        headers={"X-Proxy-Token": "secret", "X-Proxy-Source": "central"},
    )
    direct_response = client.get(
        "/proxy/info",
        headers={"X-Proxy-Token": "secret", "X-Forward-To": "1.1.1.1:80"},
    )

    assert provider_response.status_code == 404
    assert direct_response.status_code == 404


def test_start_invokes_uvicorn_with_env(monkeypatch):
    import sys

    from port_checker import main

    called = {}

    class _UV:
        class config:
            LOGGING_CONFIG = {"formatters": {"access": {"fmt": ""}}}

        def run(
            self,
            app,
            host,
            port,
            reload,
            log_level,
            log_config,
            timeout_keep_alive,
            limit_concurrency,
        ):
            called.update(
                {
                    "app": app,
                    "host": host,
                    "port": port,
                    "reload": reload,
                    "log_level": log_level,
                }
            )

    monkeypatch.setitem(sys.modules, "uvicorn", _UV())
    monkeypatch.setenv("PORT_CHECKER_HOST", "127.0.0.1")
    monkeypatch.setenv("PORT_CHECKER_PORT", "9100")
    monkeypatch.setenv("PORT_CHECKER_DEBUG", "true")

    main.start()

    assert called["host"] == "127.0.0.1"
    assert called["port"] == 9100
    assert called["reload"] is True
    assert called["log_level"] == "debug"
