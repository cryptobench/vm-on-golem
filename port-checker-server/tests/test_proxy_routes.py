import os
import types
import json
import asyncio
from typing import Any, Dict

import importlib
from fastapi.testclient import TestClient


def setup_app(monkeypatch, env: Dict[str, str]):
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    # Reload module to pick up env
    if "port_checker.main" in list(importlib.sys.modules.keys()):
        importlib.reload(importlib.import_module("port_checker.main"))
    m = importlib.import_module("port_checker.main")
    return m, TestClient(m.app)


class _StubResp:
    def __init__(self, status: int, headers: Dict[str, str] | None = None, body: bytes | None = None, json_obj: Any | None = None):
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
        self.routes = routes  # maps (METHOD, URL) => _StubResp or {"raise": "timeout"|"client"}
        self.last = {}  # maps (METHOD, URL) => kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def _handle(self, method: str, url: str, **kwargs):
        key = (method.upper(), url)
        if key not in self.routes:
            raise AssertionError(f"No stub for {key}")
        self.last[key] = kwargs
        val = self.routes[key]
        if isinstance(val, dict) and val.get("raise") == "timeout":
            raise asyncio.TimeoutError()
        if isinstance(val, dict) and val.get("raise") == "client":
            raise self.client_error_cls("boom")
        return val

    def get(self, url: str, **kwargs):
        return self._handle("GET", url, **kwargs)

    def request(self, method: str, url: str, **kwargs):
        return self._handle(method, url, **kwargs)


def test_health_and_direct_disabled(monkeypatch):
    m, client = setup_app(monkeypatch, {
        "PORT_CHECKER_PROXY_ENABLED": "true",
        "PORT_CHECKER_PROXY_ALLOW_DIRECT_IP": "false",
        "PORT_CHECKER_PROXY_TOKEN": "secret",
    })

    # Health works
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"

    # Direct proxy is disabled even with token
    r = client.get(
        "/proxy/status",
        headers={"X-Forward-To": "1.1.1.1:80", "X-Proxy-Token": "secret"}
    )
    assert r.status_code == 404


def test_provider_proxy_discovery_success(monkeypatch):
    # Prepare stubbed aiohttp session
    adv_url = "http://localhost:9001/api/v1/advertisements/prov123"
    upstream_url = "http://1.1.1.1:8080/status?foo=bar"

    routes = {
        ("GET", adv_url): _StubResp(200, json_obj={"ip_address": "1.1.1.1"}),
        ("GET", upstream_url): _StubResp(200, headers={"Server": "prov", "Connection": "keep-alive"}, body=b"OK"),
    }

    m, client = setup_app(monkeypatch, {
        "PORT_CHECKER_PROXY_ENABLED": "true",
        "PORT_CHECKER_PROXY_TOKEN": "secret",
        "DISCOVERY_API_URL": "http://localhost:9001/api/v1",
    })

    # Patch aiohttp.ClientSession used in module
    session = _StubSession(routes)
    class _ClientError(Exception):
        pass
    _StubSession.client_error_cls = _ClientError
    monkeypatch.setattr(m, "aiohttp", types.SimpleNamespace(ClientSession=lambda timeout=None: session, ClientTimeout=lambda **kw: object(), ClientError=_ClientError))

    r = client.get(
        "/proxy/provider/prov123/status?port=8080&foo=bar",
        headers={"X-Proxy-Token": "secret", "X-Proxy-Source": "discovery"},
    )
    assert r.status_code == 200
    assert r.content == b"OK"
    assert r.headers.get("Server") == "prov"
    assert r.headers.get("X-Proxy") == "golem-port-checker"
    # Hop-by-hop header stripped
    assert "Connection" not in r.headers

    # Verify forwarded tracing headers were attached
    key = ("GET", upstream_url)
    sent_headers = session.last.get(key, {}).get("headers", {})
    assert "X-Real-IP" in sent_headers
    assert "X-Forwarded-For" in sent_headers


def test_provider_proxy_missing_token(monkeypatch):
    m, client = setup_app(monkeypatch, {
        "PORT_CHECKER_PROXY_ENABLED": "true",
        "PORT_CHECKER_PROXY_TOKEN": "secret",
    })
    r = client.get("/proxy/provider/prov/status")
    assert r.status_code == 403


def test_provider_proxy_disallowed_port(monkeypatch):
    m, client = setup_app(monkeypatch, {
        "PORT_CHECKER_PROXY_ENABLED": "true",
        "PORT_CHECKER_PROXY_TOKEN": "secret",
        "PORT_CHECKER_PROXY_ALLOWED_PORTS": "80,443",
        "DISCOVERY_API_URL": "http://localhost:9001/api/v1",
    })
    # Even before network calls, port is rejected
    r = client.get(
        "/proxy/provider/prov/status?port=8080",
        headers={"X-Proxy-Token": "secret", "X-Proxy-Source": "discovery"},
    )
    assert r.status_code == 403


def test_provider_proxy_body_too_large(monkeypatch):
    adv_url = "http://localhost:9001/api/v1/advertisements/pid"
    routes = {
        ("GET", adv_url): _StubResp(200, json_obj={"ip_address": "1.2.3.4"}),
    }
    m, client = setup_app(monkeypatch, {
        "PORT_CHECKER_PROXY_ENABLED": "true",
        "PORT_CHECKER_PROXY_TOKEN": "secret",
        "DISCOVERY_API_URL": "http://localhost:9001/api/v1",
        "PORT_CHECKER_PROXY_MAX_BODY_BYTES": "10",
    })
    session = _StubSession(routes)
    class _ClientError(Exception):
        pass
    _StubSession.client_error_cls = _ClientError
    monkeypatch.setattr(m, "aiohttp", types.SimpleNamespace(ClientSession=lambda timeout=None: session, ClientTimeout=lambda **kw: object(), ClientError=_ClientError))
    r = client.post(
        "/proxy/provider/pid/upload?port=80",
        headers={"X-Proxy-Token": "secret", "X-Proxy-Source": "discovery"},
        data=b"01234567890",
    )
    assert r.status_code == 413


def test_provider_proxy_discovery_timeout(monkeypatch):
    adv_url = "http://localhost:9001/api/v1/advertisements/slow"
    routes = {
        ("GET", adv_url): {"raise": "timeout"},
    }
    m, client = setup_app(monkeypatch, {
        "PORT_CHECKER_PROXY_ENABLED": "true",
        "PORT_CHECKER_PROXY_TOKEN": "secret",
        "DISCOVERY_API_URL": "http://localhost:9001/api/v1",
    })
    session = _StubSession(routes)
    class _ClientError(Exception):
        pass
    _StubSession.client_error_cls = _ClientError
    monkeypatch.setattr(m, "aiohttp", types.SimpleNamespace(ClientSession=lambda timeout=None: session, ClientTimeout=lambda **kw: object(), ClientError=_ClientError))
    r = client.get(
        "/proxy/provider/slow/status?port=80",
        headers={"X-Proxy-Token": "secret", "X-Proxy-Source": "discovery"},
    )
    assert r.status_code == 504


def test_provider_proxy_upstream_client_error(monkeypatch):
    adv_url = "http://localhost:9001/api/v1/advertisements/prov"
    upstream = "http://1.2.3.4:80/fail"
    routes = {
        ("GET", adv_url): _StubResp(200, json_obj={"ip_address": "1.2.3.4"}),
        ("GET", upstream): {"raise": "client"},
    }
    m, client = setup_app(monkeypatch, {
        "PORT_CHECKER_PROXY_ENABLED": "true",
        "PORT_CHECKER_PROXY_TOKEN": "secret",
        "DISCOVERY_API_URL": "http://localhost:9001/api/v1",
    })
    session = _StubSession(routes)
    class _ClientError(Exception):
        pass
    _StubSession.client_error_cls = _ClientError
    monkeypatch.setattr(m, "aiohttp", types.SimpleNamespace(ClientSession=lambda timeout=None: session, ClientTimeout=lambda **kw: object(), ClientError=_ClientError))
    r = client.get(
        "/proxy/provider/prov/fail?port=80",
        headers={"X-Proxy-Token": "secret", "X-Proxy-Source": "discovery"},
    )
    assert r.status_code == 502


def test_provider_proxy_discovery_not_found(monkeypatch):
    adv_url = "http://localhost:9001/api/v1/advertisements/missing"
    routes = {
        ("GET", adv_url): _StubResp(404, json_obj={"detail": "not found"}),
    }
    m, client = setup_app(monkeypatch, {
        "PORT_CHECKER_PROXY_ENABLED": "true",
        "PORT_CHECKER_PROXY_TOKEN": "secret",
        "DISCOVERY_API_URL": "http://localhost:9001/api/v1",
    })
    class _ClientError(Exception):
        pass
    monkeypatch.setattr(m, "aiohttp", types.SimpleNamespace(ClientSession=lambda timeout=None: _StubSession(routes), ClientTimeout=lambda **kw: object(), ClientError=_ClientError))
    r = client.get(
        "/proxy/provider/missing/status?port=80",
        headers={"X-Proxy-Token": "secret", "X-Proxy-Source": "discovery"},
    )
    assert r.status_code == 404


def test_provider_proxy_golem_base_not_installed(monkeypatch):
    m, client = setup_app(monkeypatch, {
        "PORT_CHECKER_PROXY_ENABLED": "true",
        "PORT_CHECKER_PROXY_TOKEN": "secret",
        # No GOLEM_BASE_* set, and SDK likely not importable during tests
    })
    # Ensure code path treats SDK as not available
    monkeypatch.setattr(importlib.import_module("port_checker.main"), "_HAS_GOLEM_BASE", False, raising=False)
    r = client.get(
        "/proxy/provider/prov/status?port=80",
        headers={"X-Proxy-Token": "secret", "X-Proxy-Source": "golem-base"},
    )
    assert r.status_code in (501, 500)


def test_provider_proxy_golem_base_success(monkeypatch):
    # Upstream provider URL (after resolution via Golem Base)
    upstream_url = "http://3.4.5.6:8080/status?foo=bar"

    # Stub upstream response through aiohttp
    routes = {
        ("GET", upstream_url): _StubResp(200, headers={"Server": "prov"}, body=b"OK"),
    }

    m, client = setup_app(
        monkeypatch,
        {
            "PORT_CHECKER_PROXY_ENABLED": "true",
            "PORT_CHECKER_PROXY_TOKEN": "secret",
            # Set defaults (these should be overrideable by headers below)
            "GOLEM_BASE_RPC_URL": "http://rpc.default",
            "GOLEM_BASE_WS_URL": "ws://ws.default",
        },
    )

    # Patch aiohttp session
    session = _StubSession(routes)
    monkeypatch.setattr(
        m,
        "aiohttp",
        types.SimpleNamespace(
            ClientSession=lambda timeout=None: session,
            ClientTimeout=lambda **kw: object(),
            ClientError=Exception,
        ),
    )

    # Minimal stub for Golem Base client
    created_kwargs = {}

    class _GBStub:
        async def query_entities(self, query: str):  # return one match
            assert "golem_provider_id" in query
            # entity_key needs to be a hex string understood by GenericBytes.from_hex_string
            return [types.SimpleNamespace(entity_key="0x" + ("00" * 32))]

        async def get_entity_metadata(self, _ek):
            # Provide string annotation with public IP
            return types.SimpleNamespace(
                string_annotations=[
                    types.SimpleNamespace(key="golem_ip_address", value="3.4.5.6")
                ]
            )

        async def disconnect(self):
            return None

    async def _create(**kwargs):
        # Capture that header overrides are used
        created_kwargs.update(kwargs)
        return _GBStub()

    monkeypatch.setattr(m, "GolemBaseClient", types.SimpleNamespace(create=_create))
    monkeypatch.setattr(m, "_HAS_GOLEM_BASE", True)

    # Call with header overrides for RPC/WS to exercise that branch
    r = client.get(
        "/proxy/provider/prov123/status?port=8080&foo=bar",
        headers={
            "X-Proxy-Token": "secret",
            "X-Proxy-Source": "golem-base",
            "X-Proxy-Golem-Base-Rpc": "http://rpc.override",
            "X-Proxy-Golem-Base-Ws": "ws://ws.override",
        },
    )
    assert r.status_code == 200
    assert r.content == b"OK"
    assert r.headers.get("Server") == "prov"
    assert r.headers.get("X-Proxy-Provider-Id") == "prov123"

    # Verify header overrides were honored in client creation
    assert created_kwargs.get("rpc_url") == "http://rpc.override"
    assert created_kwargs.get("ws_url") == "ws://ws.override"

    # Verify forwarded tracing headers were attached
    sent_headers = session.last.get(("GET", upstream_url), {}).get("headers", {})
    assert "X-Real-IP" in sent_headers
    assert "X-Forwarded-For" in sent_headers


def test_provider_proxy_golem_base_not_found(monkeypatch):
    # When Golem Base returns no entities, we should get 404
    m, client = setup_app(
        monkeypatch,
        {
            "PORT_CHECKER_PROXY_ENABLED": "true",
            "PORT_CHECKER_PROXY_TOKEN": "secret",
            "GOLEM_BASE_RPC_URL": "http://rpc",
            "GOLEM_BASE_WS_URL": "ws://ws",
        },
    )

    class _GBStub:
        async def query_entities(self, query: str):
            return []

        async def disconnect(self):
            return None

    async def _create(**kwargs):  # noqa: ARG001
        return _GBStub()

    monkeypatch.setattr(m, "GolemBaseClient", types.SimpleNamespace(create=_create))
    monkeypatch.setattr(m, "_HAS_GOLEM_BASE", True)

    r = client.get(
        "/proxy/provider/prov/status?port=80",
        headers={"X-Proxy-Token": "secret", "X-Proxy-Source": "golem-base"},
    )
    assert r.status_code == 404


def test_provider_proxy_golem_base_missing_urls(monkeypatch):
    # If SDK is installed (_HAS_GOLEM_BASE True) but URLs are missing, return 500
    m, client = setup_app(
        monkeypatch,
        {
            "PORT_CHECKER_PROXY_ENABLED": "true",
            "PORT_CHECKER_PROXY_TOKEN": "secret",
            # Intentionally omit GOLEM_BASE_* envs
        },
    )
    monkeypatch.setattr(m, "_HAS_GOLEM_BASE", True)

    r = client.get(
        "/proxy/provider/prov/status?port=80",
        headers={"X-Proxy-Token": "secret", "X-Proxy-Source": "golem-base"},
    )
    assert r.status_code == 500


def test_direct_ip_enabled_with_token(monkeypatch):
    # When direct IP is enabled, verify forwarding works and removes target param
    routes = {
        ("GET", "http://2.2.2.2:8000/info?foo=bar"): _StubResp(200, headers={"Server": "prov", "Connection": "keep-alive"}, body=b"DIRECT"),
    }
    m, client = setup_app(monkeypatch, {
        "PORT_CHECKER_PROXY_ENABLED": "true",
        "PORT_CHECKER_PROXY_ALLOW_DIRECT_IP": "true",
        "PORT_CHECKER_PROXY_TOKEN": "secret",
    })
    monkeypatch.setattr(m, "aiohttp", types.SimpleNamespace(ClientSession=lambda timeout=None: _StubSession(routes), ClientTimeout=lambda **kw: object()))
    r = client.get(
        "/proxy/info?foo=bar&target=shouldremove",
        headers={
            "X-Forward-To": "2.2.2.2:8000",
            "X-Proxy-Token": "secret",
        },
    )
    assert r.status_code == 200
    assert r.content == b"DIRECT"
    assert r.headers.get("Server") == "prov"
    assert "Connection" not in r.headers


def test_provider_proxy_golem_base_error_and_invalid_ip(monkeypatch):
    # First: client raise -> 502
    m, client = setup_app(
        monkeypatch,
        {
            "PORT_CHECKER_PROXY_ENABLED": "true",
            "PORT_CHECKER_PROXY_TOKEN": "secret",
            "GOLEM_BASE_RPC_URL": "http://rpc",
            "GOLEM_BASE_WS_URL": "ws://ws",
        },
    )

    async def _create_raises(**kwargs):  # noqa: ARG001
        raise RuntimeError("boom")

    monkeypatch.setattr(m, "GolemBaseClient", types.SimpleNamespace(create=_create_raises))
    monkeypatch.setattr(m, "_HAS_GOLEM_BASE", True)
    r = client.get(
        "/proxy/provider/prov/status",
        headers={"X-Proxy-Token": "secret", "X-Proxy-Source": "golem-base"},
    )
    assert r.status_code == 502

    # Second: invalid resolved IP -> 400
    class _GBStub:
        async def query_entities(self, query: str):
            return [types.SimpleNamespace(entity_key="0x" + ("00" * 32))]

        async def get_entity_metadata(self, _ek):
            return types.SimpleNamespace(
                string_annotations=[types.SimpleNamespace(key="golem_ip_address", value="127.0.0.1")]
            )

        async def disconnect(self):
            return None

    async def _create_ok(**kwargs):  # noqa: ARG001
        return _GBStub()

    monkeypatch.setattr(m, "GolemBaseClient", types.SimpleNamespace(create=_create_ok))
    r = client.get(
        "/proxy/provider/prov/status",
        headers={"X-Proxy-Token": "secret", "X-Proxy-Source": "golem-base"},
    )
    assert r.status_code == 400


def test_provider_default_port_no_query(monkeypatch):
    # Ensure provider proxy handles empty querystring path (exercises qs_forward else)
    adv_url = "http://localhost:9001/api/v1/advertisements/pdef"
    upstream_url = "http://1.1.1.1:80/status"
    routes = {
        ("GET", adv_url): _StubResp(200, json_obj={"ip_address": "1.1.1.1"}),
        ("GET", upstream_url): _StubResp(200, body=b"OK"),
    }
    m, client = setup_app(monkeypatch, {
        "PORT_CHECKER_PROXY_ENABLED": "true",
        "PORT_CHECKER_PROXY_TOKEN": "secret",
        "DISCOVERY_API_URL": "http://localhost:9001/api/v1",
    })
    session = _StubSession(routes)
    monkeypatch.setattr(m, "aiohttp", types.SimpleNamespace(ClientSession=lambda timeout=None: session, ClientTimeout=lambda **kw: object(), ClientError=Exception))
    r = client.get(
        "/proxy/provider/pdef/status",
        headers={"X-Proxy-Token": "secret"},
    )
    assert r.status_code == 200


def test_proxy_disabled_for_both_routes(monkeypatch):
    # Provider path
    m, client = setup_app(monkeypatch, {
        "PORT_CHECKER_PROXY_ENABLED": "false",
        "PORT_CHECKER_PROXY_TOKEN": "secret",
    })
    r = client.get(
        "/proxy/provider/prov/status?port=80",
        headers={"X-Proxy-Token": "secret", "X-Proxy-Source": "discovery"},
    )
    assert r.status_code == 404

    # Direct path
    r = client.get(
        "/proxy/info",
        headers={"X-Proxy-Token": "secret", "X-Forward-To": "1.1.1.1:80"},
    )
    assert r.status_code == 404


def test_discovery_client_error(monkeypatch):
    adv_url = "http://localhost:9001/api/v1/advertisements/provCE"
    routes = {
        ("GET", adv_url): {"raise": "client"},
    }
    m, client = setup_app(monkeypatch, {
        "PORT_CHECKER_PROXY_ENABLED": "true",
        "PORT_CHECKER_PROXY_TOKEN": "secret",
        "DISCOVERY_API_URL": "http://localhost:9001/api/v1",
    })
    session = _StubSession(routes)
    class _ClientError(Exception):
        pass
    _StubSession.client_error_cls = _ClientError
    monkeypatch.setattr(m, "aiohttp", types.SimpleNamespace(ClientSession=lambda timeout=None: session, ClientTimeout=lambda **kw: object(), ClientError=_ClientError))
    r = client.get(
        "/proxy/provider/provCE/status?port=80",
        headers={"X-Proxy-Token": "secret", "X-Proxy-Source": "discovery"},
    )
    assert r.status_code == 502


def test_provider_upstream_timeout(monkeypatch):
    adv_url = "http://localhost:9001/api/v1/advertisements/provTO"
    upstream = "http://1.2.3.4:80/slow"
    routes = {
        ("GET", adv_url): _StubResp(200, json_obj={"ip_address": "1.2.3.4"}),
        ("GET", upstream): {"raise": "timeout"},
    }
    m, client = setup_app(monkeypatch, {
        "PORT_CHECKER_PROXY_ENABLED": "true",
        "PORT_CHECKER_PROXY_TOKEN": "secret",
        "DISCOVERY_API_URL": "http://localhost:9001/api/v1",
    })
    session = _StubSession(routes)
    class _ClientError(Exception):
        pass
    _StubSession.client_error_cls = _ClientError
    monkeypatch.setattr(m, "aiohttp", types.SimpleNamespace(ClientSession=lambda timeout=None: session, ClientTimeout=lambda **kw: object(), ClientError=_ClientError))
    r = client.get(
        "/proxy/provider/provTO/slow?port=80",
        headers={"X-Proxy-Token": "secret", "X-Proxy-Source": "discovery"},
    )
    assert r.status_code == 504


def test_direct_ip_invalid_port_string(monkeypatch):
    m, client = setup_app(monkeypatch, {
        "PORT_CHECKER_PROXY_ENABLED": "true",
        "PORT_CHECKER_PROXY_ALLOW_DIRECT_IP": "true",
        "PORT_CHECKER_PROXY_TOKEN": "secret",
    })
    r = client.get(
        "/proxy/info",
        headers={"X-Proxy-Token": "secret", "X-Forward-To": "1.1.1.1:abc"},
    )
    assert r.status_code == 400


def test_direct_ip_no_query_and_body_too_large(monkeypatch):
    routes = {
        ("GET", "http://8.8.8.8:8080/info"): _StubResp(200, body=b"OK"),
    }
    m, client = setup_app(monkeypatch, {
        "PORT_CHECKER_PROXY_ENABLED": "true",
        "PORT_CHECKER_PROXY_ALLOW_DIRECT_IP": "true",
        "PORT_CHECKER_PROXY_TOKEN": "secret",
        "PORT_CHECKER_PROXY_MAX_BODY_BYTES": "3",
    })
    monkeypatch.setattr(m, "aiohttp", types.SimpleNamespace(ClientSession=lambda timeout=None: _StubSession(routes), ClientTimeout=lambda **kw: object(), ClientError=Exception))
    # No query string -> exercises qs_forward else branch
    r = client.get(
        "/proxy/info",
        headers={"X-Proxy-Token": "secret", "X-Forward-To": "8.8.8.8:8080"},
    )
    assert r.status_code == 200

    # Now exceed body size to hit 413 in direct proxy
    r = client.post(
        "/proxy/upload",
        headers={"X-Proxy-Token": "secret", "X-Forward-To": "8.8.8.8:8080"},
        data=b"toolong",
    )
    assert r.status_code == 413


def test_direct_ip_timeout_and_client_error(monkeypatch):
    routes = {
        ("GET", "http://9.9.9.9:8080/slow"): {"raise": "timeout"},
        ("GET", "http://9.9.9.9:8080/fail"): {"raise": "client"},
    }
    m, client = setup_app(monkeypatch, {
        "PORT_CHECKER_PROXY_ENABLED": "true",
        "PORT_CHECKER_PROXY_ALLOW_DIRECT_IP": "true",
        "PORT_CHECKER_PROXY_TOKEN": "secret",
    })
    session = _StubSession(routes)
    class _ClientError(Exception):
        pass
    _StubSession.client_error_cls = _ClientError
    monkeypatch.setattr(m, "aiohttp", types.SimpleNamespace(ClientSession=lambda timeout=None: session, ClientTimeout=lambda **kw: object(), ClientError=_ClientError))

    r = client.get(
        "/proxy/slow",
        headers={"X-Proxy-Token": "secret", "X-Forward-To": "9.9.9.9:8080"},
    )
    assert r.status_code == 504

    r = client.get(
        "/proxy/fail",
        headers={"X-Proxy-Token": "secret", "X-Forward-To": "9.9.9.9:8080"},
    )
    assert r.status_code == 502


def test_start_invokes_uvicorn_with_env(monkeypatch):
    # Patch uvicorn.run to capture invocation and avoid starting a server
    import importlib, types, sys
    m = importlib.import_module("port_checker.main")
    called = {}

    class _UV:
        class config:
            LOGGING_CONFIG = {"formatters": {"access": {"fmt": ""}}}

        def run(self, app, host, port, reload, log_level, log_config, timeout_keep_alive, limit_concurrency):  # noqa: ARG002
            called.update(dict(app=app, host=host, port=port, reload=reload, log_level=log_level))

    # Patch modules so that `import uvicorn` and `from dotenv import load_dotenv` succeed
    monkeypatch.setitem(sys.modules, "uvicorn", _UV())
    monkeypatch.setitem(sys.modules, "dotenv", types.SimpleNamespace(load_dotenv=lambda dotenv_path=None: None))
    monkeypatch.setenv("PORT_CHECKER_HOST", "127.0.0.1")
    monkeypatch.setenv("PORT_CHECKER_PORT", "9100")
    monkeypatch.setenv("PORT_CHECKER_DEBUG", "true")
    m.start()
    assert called.get("host") == "127.0.0.1"
    assert called.get("port") == 9100
    assert called.get("reload") is True
    assert called.get("log_level") == "debug"


def test_main_guard_executes_start(monkeypatch):
    # Ensure the __main__ guard path is covered
    import runpy, os, sys, types
    called = {}

    class _UV:
        class config:
            LOGGING_CONFIG = {"formatters": {"access": {"fmt": ""}}}

        def run(self, app, host, port, reload, log_level, log_config, timeout_keep_alive, limit_concurrency):  # noqa: ARG002
            called.update(dict(app=app, host=host, port=port))

    mod_path = os.path.join(os.path.dirname(__file__), "..", "port_checker", "main.py")
    mod_path = os.path.abspath(mod_path)

    # Ensure imports inside start() resolve
    monkeypatch.setitem(sys.modules, "uvicorn", _UV())
    monkeypatch.setitem(sys.modules, "dotenv", types.SimpleNamespace(load_dotenv=lambda dotenv_path=None: None))
    # Execute module as __main__ with uvicorn patched via run_globals
    run_globals = {"__name__": "__main__", "__file__": mod_path}
    run_globals["__package__"] = None
    with open(mod_path, "rb") as f:
        code = compile(f.read(), mod_path, "exec")
    exec(code, run_globals)
    assert "host" in called


def test_direct_ip_enabled_missing_token(monkeypatch):
    m, client = setup_app(monkeypatch, {
        "PORT_CHECKER_PROXY_ENABLED": "true",
        "PORT_CHECKER_PROXY_ALLOW_DIRECT_IP": "true",
        "PORT_CHECKER_PROXY_TOKEN": "secret",
    })
    r = client.get(
        "/proxy/info",
        headers={"X-Forward-To": "2.2.2.2:8000"},
    )
    assert r.status_code == 403


def test_direct_ip_invalid_target_and_protocol(monkeypatch):
    m, client = setup_app(monkeypatch, {
        "PORT_CHECKER_PROXY_ENABLED": "true",
        "PORT_CHECKER_PROXY_ALLOW_DIRECT_IP": "true",
        "PORT_CHECKER_PROXY_TOKEN": "secret",
    })
    # Missing X-Forward-To
    r = client.get(
        "/proxy/info",
        headers={"X-Proxy-Token": "secret"},
    )
    assert r.status_code == 400
    # Invalid protocol
    r = client.get(
        "/proxy/info",
        headers={"X-Proxy-Token": "secret", "X-Forward-To": "2.2.2.2:80", "X-Forward-Protocol": "https"},
    )
    assert r.status_code == 400


def test_direct_ip_non_public_and_disallowed_port(monkeypatch):
    routes = {}
    m, client = setup_app(monkeypatch, {
        "PORT_CHECKER_PROXY_ENABLED": "true",
        "PORT_CHECKER_PROXY_ALLOW_DIRECT_IP": "true",
        "PORT_CHECKER_PROXY_TOKEN": "secret",
        "PORT_CHECKER_PROXY_ALLOWED_PORTS": "80",
    })
    monkeypatch.setattr(m, "aiohttp", types.SimpleNamespace(ClientSession=lambda timeout=None: _StubSession(routes), ClientTimeout=lambda **kw: object(), ClientError=Exception))
    # Non-public
    r = client.get(
        "/proxy/info",
        headers={"X-Proxy-Token": "secret", "X-Forward-To": "127.0.0.1:80"},
    )
    assert r.status_code == 400
    # Disallowed port
    r = client.get(
        "/proxy/info",
        headers={"X-Proxy-Token": "secret", "X-Forward-To": "1.1.1.1:81"},
    )
    assert r.status_code == 403


def test_provider_invalid_source_and_token_mismatch(monkeypatch):
    m, client = setup_app(monkeypatch, {
        "PORT_CHECKER_PROXY_ENABLED": "true",
        "PORT_CHECKER_PROXY_TOKEN": "secret",
    })
    # Invalid source
    r = client.get(
        "/proxy/provider/prov/status?port=80",
        headers={"X-Proxy-Token": "secret", "X-Proxy-Source": "invalid"},
    )
    assert r.status_code == 400
    # Token mismatch
    r = client.get(
        "/proxy/provider/prov/status?port=80",
        headers={"X-Proxy-Token": "wrong", "X-Proxy-Source": "discovery"},
    )
    assert r.status_code == 403
