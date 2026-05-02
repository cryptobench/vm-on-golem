import asyncio

from fastapi.testclient import TestClient

from port_checker.app import create_app
from port_checker.config import Settings
from port_checker.ports.api import get_port_check_service
from port_checker.ports.service import PortCheckService


class _DummyWriter:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True

    async def wait_closed(self):
        return None


async def _no_sleep(delay: float):
    return None


def test_check_ports_endpoint_success_and_fail():
    async def fake_open_connection(host, port):
        if port == 80:
            return object(), _DummyWriter()
        raise ConnectionRefusedError()

    app = create_app(
        Settings(
            PORT_CHECK_RETRIES=1,
            PORT_CHECK_RETRY_DELAY=0,
            PORT_CHECK_TIMEOUT=0.1,
        )
    )
    app.dependency_overrides[get_port_check_service] = lambda: PortCheckService(
        retries=1,
        retry_delay=0,
        timeout=0.1,
        open_connection=fake_open_connection,
        sleep=_no_sleep,
    )
    client = TestClient(app)

    response = client.post(
        "/check-ports",
        json={"provider_ip": "8.8.8.8", "ports": [80, 1234]},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["results"]["80"]["accessible"] is True
    assert data["results"]["1234"]["accessible"] is False


def test_check_ports_validator_rejects_out_of_range():
    client = TestClient(create_app(Settings()))

    response = client.post(
        "/check-ports",
        json={"provider_ip": "1.2.3.4", "ports": [80, 70000]},
    )

    assert response.status_code == 422


def test_port_check_service_handles_timeout_and_generic_error():
    async def timeout(host, port):
        raise asyncio.TimeoutError()

    async def generic(host, port):
        raise RuntimeError("boom")

    timeout_service = PortCheckService(
        retries=1, open_connection=timeout, sleep=_no_sleep
    )
    generic_service = PortCheckService(
        retries=1, open_connection=generic, sleep=_no_sleep
    )

    timeout_result = asyncio.run(timeout_service.check_port("1.2.3.4", 80))
    generic_result = asyncio.run(generic_service.check_port("1.2.3.4", 80))

    assert timeout_result.accessible is False
    assert timeout_result.error == "Connection timed out"
    assert generic_result.accessible is False
    assert generic_result.error == "boom"
