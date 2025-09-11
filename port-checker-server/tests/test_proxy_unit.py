import importlib
import os
import sys
import asyncio

# Ensure local package is importable (prefer local over any installed version)
TEST_DIR = os.path.dirname(__file__)
PKG_ROOT = os.path.abspath(os.path.join(TEST_DIR, ".."))
if PKG_ROOT not in sys.path:
    sys.path.insert(0, PKG_ROOT)


def test_parse_allowed_ports_basic():
    m = importlib.import_module("port_checker.main")
    parse = getattr(m, "_parse_allowed_ports")

    ranges = parse("80,443,1000-1005,  65535")
    assert (80, 80) in ranges
    assert (443, 443) in ranges
    assert (1000, 1005) in ranges
    assert (65535, 65535) in ranges


def test_is_public_ip_recognizes_private_and_public():
    m = importlib.import_module("port_checker.main")
    is_pub = getattr(m, "_is_public_ip")

    # Private and loopback should be rejected
    assert is_pub("127.0.0.1") is False
    assert is_pub("10.0.0.1") is False
    assert is_pub("192.168.1.10") is False
    # Clearly public
    assert is_pub("1.1.1.1") is True


def test_is_allowed_port_range_and_exact():
    m = importlib.import_module("port_checker.main")
    # Use module's parsed ranges
    is_allowed = getattr(m, "_is_allowed_port")

    assert is_allowed(80)
    assert is_allowed(443)
    assert is_allowed(5000)
    assert is_allowed(65535)
    assert is_allowed(1024)
    assert is_allowed(2048)


def test_parse_allowed_ports_wildcard():
    m = importlib.import_module("port_checker.main")
    parse = getattr(m, "_parse_allowed_ports")
    ranges = parse("*")
    assert (1, 65535) in ranges


def test_parse_allowed_ports_invalid_tokens_skipped():
    m = importlib.import_module("port_checker.main")
    parse = getattr(m, "_parse_allowed_ports")
    # Include invalid range token and invalid integer token; they should be skipped
    ranges = parse("80,abc-def,notanint,443")
    assert (80, 80) in ranges
    assert (443, 443) in ranges
    # Ensure no bogus ranges were added
    assert all(isinstance(t, tuple) and len(t) == 2 for t in ranges)


def test_is_public_ip_rejects_invalid_string():
    m = importlib.import_module("port_checker.main")
    is_pub = getattr(m, "_is_public_ip")
    assert is_pub("not.an.ip") is False


def test_check_ports_validator_rejects_out_of_range(monkeypatch):
    # Use FastAPI client to trigger Pydantic validation error path
    import importlib
    from fastapi.testclient import TestClient

    m = importlib.import_module("port_checker.main")
    client = TestClient(m.app)
    r = client.post("/check-ports", json={"provider_ip": "1.2.3.4", "ports": [80, 70000]})
    assert r.status_code == 422


async def _fake_open_connection_timeout(host, port):  # noqa: ARG001
    raise asyncio.TimeoutError()


async def _fake_open_connection_generic(host, port):  # noqa: ARG001
    raise RuntimeError("boom")


def test_check_port_handles_timeout_and_generic(monkeypatch):
    m = importlib.import_module("port_checker.main")

    # Patch open_connection to timeout
    monkeypatch.setattr(m.asyncio, "open_connection", _fake_open_connection_timeout)
    res = m.asyncio.get_event_loop().run_until_complete(m.check_port("1.2.3.4", 80, retries=1))
    assert res.accessible is False and "timed out" in (res.error or "")

    # Patch to generic error
    monkeypatch.setattr(m.asyncio, "open_connection", _fake_open_connection_generic)
    res = m.asyncio.get_event_loop().run_until_complete(m.check_port("1.2.3.4", 80, retries=1))
    assert res.accessible is False and "boom" in (res.error or "")
