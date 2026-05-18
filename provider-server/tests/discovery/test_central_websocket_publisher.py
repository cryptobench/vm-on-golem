import asyncio
from contextlib import suppress

import aiohttp
import pytest
from eth_account import Account
from eth_account.messages import encode_defunct

from provider.config import settings
from provider.discovery.publishers import (
    CentralDiscoveryPublisher,
    provider_auth_message,
)


PRIVATE_KEY = "0x" + "11" * 32
PROVIDER_ID = Account.from_key(PRIVATE_KEY).address


class StubResourceTracker:
    def __init__(self, resources, meets_minimum=True):
        self._resources = resources
        self._meets_minimum = meets_minimum
        self.callbacks = []

    def get_available_resources(self):
        return self._resources

    def _meets_minimum_requirements(self, resources):
        return self._meets_minimum

    def on_update(self, callback):
        self.callbacks.append(callback)


class StubCertificateService:
    def __init__(self, advertisable):
        self.advertisable = advertisable

    def endpoint_is_advertisable(self):
        return self.advertisable


class StubWebSocket:
    def __init__(self, incoming=None, messages=None):
        self.incoming = list(
            incoming
            or [
                {"type": "hello", "nonce": "nonce-1"},
                {"type": "authenticated", "provider_id": PROVIDER_ID},
            ]
        )
        self.messages = list(messages or [])
        self.sent = []
        self.closed = False

    async def receive_json(self):
        return self.incoming.pop(0)

    async def send_json(self, payload):
        self.sent.append(payload)

    async def close(self):
        self.closed = True

    def exception(self):
        return RuntimeError("stub websocket error")

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.messages:
            message = self.messages.pop(0)
            if isinstance(message, BaseException):
                raise message
            if message is None:
                raise StopAsyncIteration
            return message
        await asyncio.Future()
        raise StopAsyncIteration


class StubSession:
    def __init__(self, *connections):
        self.connections = list(connections)
        self.websocket = None
        self.closed = False
        self.connect_count = 0

    async def ws_connect(self, url):
        self.connect_count += 1
        self.url = url
        connection = self.connections.pop(0)
        if isinstance(connection, BaseException):
            raise connection
        self.websocket = connection
        return self.websocket

    async def close(self):
        self.closed = True


class StubMessage:
    def __init__(self, message_type):
        self.type = message_type


def use_fast_reconnect(publisher):
    publisher._initial_reconnect_delay_seconds = 0.01
    publisher._reconnect_delay_seconds = 0.01
    publisher._max_reconnect_delay_seconds = 0.01


async def wait_until(predicate, timeout=1.0):
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("timed out waiting for condition")


async def stop_loop(publisher, task):
    await publisher.stop()
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


@pytest.fixture(autouse=True)
def provider_identity(monkeypatch):
    monkeypatch.setattr(settings, "ETHEREUM_PRIVATE_KEY", PRIVATE_KEY)
    monkeypatch.setattr(settings, "PROVIDER_ID", PROVIDER_ID)
    monkeypatch.setattr(settings, "PUBLIC_IP", "127.0.0.1")


def test_central_publisher_signs_auth_payload():
    publisher = CentralDiscoveryPublisher(
        StubResourceTracker({"cpu": 2, "memory": 2, "storage": 10})
    )
    timestamp = "2026-05-17T12:00:00+00:00"

    signature = publisher._sign_auth("nonce-1", timestamp)
    recovered = Account.recover_message(
        encode_defunct(text=provider_auth_message(PROVIDER_ID, "nonce-1", timestamp)),
        signature=signature,
    )

    assert recovered == PROVIDER_ID


@pytest.mark.asyncio
async def test_start_loop_connects_authenticates_and_publishes(monkeypatch):
    websocket = StubWebSocket()
    session = StubSession(websocket)
    monkeypatch.setattr(
        "provider.discovery.publishers.aiohttp.ClientSession",
        lambda *args, **kwargs: session,
    )
    tracker = StubResourceTracker({"cpu": 2, "memory": 2, "storage": 10})
    publisher = CentralDiscoveryPublisher(
        tracker,
        discovery_ws_url="ws://central/api/v1/discovery/providers",
    )

    await publisher.initialize()
    task = asyncio.create_task(publisher.start_loop())

    try:
        await wait_until(lambda: len(websocket.sent) >= 2)

        assert session.url == "ws://central/api/v1/discovery/providers"
        assert websocket.sent[0]["type"] == "authenticate"
        assert websocket.sent[1]["type"] == "advertisement.upsert"
        assert websocket.sent[1]["advertisement"]["pricing"]["usd_per_core_month"] == (
            settings.PRICE_USD_PER_CORE_MONTH
        )
    finally:
        await stop_loop(publisher, task)


@pytest.mark.asyncio
async def test_resource_update_sends_live_upsert():
    websocket = StubWebSocket([])
    tracker = StubResourceTracker({"cpu": 2, "memory": 2, "storage": 10})
    publisher = CentralDiscoveryPublisher(tracker)
    publisher.session = StubSession(websocket)
    publisher.websocket = websocket

    tracker.on_update(lambda: asyncio.create_task(publisher.post_advertisement()))
    tracker.callbacks[0]()
    await asyncio.sleep(0)

    assert websocket.sent[0]["type"] == "advertisement.upsert"


@pytest.mark.asyncio
async def test_invalid_certificate_sends_remove():
    websocket = StubWebSocket([])
    publisher = CentralDiscoveryPublisher(
        StubResourceTracker({"cpu": 2, "memory": 2, "storage": 10}),
        certificate_service=StubCertificateService(False),
    )
    publisher.session = StubSession(websocket)
    publisher.websocket = websocket

    await publisher.post_advertisement()

    assert websocket.sent == [{"type": "advertisement.remove"}]


@pytest.mark.asyncio
async def test_low_resources_send_remove():
    websocket = StubWebSocket([])
    publisher = CentralDiscoveryPublisher(
        StubResourceTracker(
            {"cpu": 0, "memory": 0, "storage": 0},
            meets_minimum=False,
        )
    )
    publisher.session = StubSession(websocket)
    publisher.websocket = websocket

    await publisher.post_advertisement()

    assert websocket.sent == [{"type": "advertisement.remove"}]


@pytest.mark.asyncio
async def test_initial_connect_failure_retries_and_later_publishes(monkeypatch, caplog):
    websocket = StubWebSocket()
    session = StubSession(RuntimeError("connect failed"), websocket)
    monkeypatch.setattr(
        "provider.discovery.publishers.aiohttp.ClientSession",
        lambda *args, **kwargs: session,
    )
    publisher = CentralDiscoveryPublisher(
        StubResourceTracker({"cpu": 2, "memory": 2, "storage": 10})
    )
    use_fast_reconnect(publisher)
    await publisher.initialize()
    task = asyncio.create_task(publisher.start_loop())

    try:
        await wait_until(lambda: len(websocket.sent) >= 2)

        assert session.connect_count == 2
        assert "Central discovery websocket unavailable" in caplog.text
        assert websocket.sent[0]["type"] == "authenticate"
        assert websocket.sent[1]["type"] == "advertisement.upsert"
    finally:
        await stop_loop(publisher, task)


@pytest.mark.asyncio
async def test_closed_websocket_reconnects_and_republishes(monkeypatch):
    first = StubWebSocket(messages=[StubMessage(aiohttp.WSMsgType.CLOSED)])
    second = StubWebSocket()
    session = StubSession(first, second)
    monkeypatch.setattr(
        "provider.discovery.publishers.aiohttp.ClientSession",
        lambda *args, **kwargs: session,
    )
    publisher = CentralDiscoveryPublisher(
        StubResourceTracker({"cpu": 2, "memory": 2, "storage": 10})
    )
    use_fast_reconnect(publisher)
    await publisher.initialize()
    task = asyncio.create_task(publisher.start_loop())

    try:
        await wait_until(lambda: len(second.sent) >= 2)

        assert session.connect_count == 2
        assert first.closed is True
        assert first.sent[1]["type"] == "advertisement.upsert"
        assert second.sent[1]["type"] == "advertisement.upsert"
    finally:
        await stop_loop(publisher, task)


@pytest.mark.asyncio
async def test_stop_cancels_retry_and_closes_session(monkeypatch):
    session = StubSession(RuntimeError("connect failed"))
    monkeypatch.setattr(
        "provider.discovery.publishers.aiohttp.ClientSession",
        lambda *args, **kwargs: session,
    )
    publisher = CentralDiscoveryPublisher(
        StubResourceTracker({"cpu": 2, "memory": 2, "storage": 10})
    )
    publisher._initial_reconnect_delay_seconds = 10
    publisher._reconnect_delay_seconds = 10
    publisher._max_reconnect_delay_seconds = 10
    await publisher.initialize()
    task = asyncio.create_task(publisher.start_loop())

    await wait_until(lambda: session.connect_count == 1)
    await publisher.stop()
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task

    assert session.closed is True
    assert session.connect_count == 1


@pytest.mark.asyncio
async def test_disconnected_resource_update_uses_single_connection(monkeypatch):
    websocket = StubWebSocket()
    session = StubSession(websocket)
    monkeypatch.setattr(
        "provider.discovery.publishers.aiohttp.ClientSession",
        lambda *args, **kwargs: session,
    )
    publisher = CentralDiscoveryPublisher(
        StubResourceTracker({"cpu": 2, "memory": 2, "storage": 10})
    )
    publisher.session = session

    await asyncio.gather(
        publisher.post_advertisement(),
        publisher.post_advertisement(),
    )

    assert session.connect_count == 1
    authenticate_events = [
        event for event in websocket.sent if event["type"] == "authenticate"
    ]
    assert (
        len(
            [
                event
                for event in websocket.sent
                if event["type"] == "advertisement.upsert"
            ]
        )
        == 2
    )
    assert len(authenticate_events) == 1
