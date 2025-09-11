import importlib
import types
import asyncio
from fastapi.testclient import TestClient


class _DummyWriter:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True

    async def wait_closed(self):
        return


def test_check_ports_success_and_fail(monkeypatch):
    m = importlib.import_module("port_checker.main")
    client = TestClient(m.app)

    async def fake_open_connection(host, port):
        if port == 80:
            return object(), _DummyWriter()
        raise ConnectionRefusedError()

    monkeypatch.setattr(asyncio, "open_connection", fake_open_connection)

    r = client.post("/check-ports", json={"provider_ip": "8.8.8.8", "ports": [80, 1234]})
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["results"]["80"]["accessible"] is True
    assert data["results"]["1234"]["accessible"] is False

