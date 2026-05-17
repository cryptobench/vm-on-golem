import asyncio

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
    def __init__(self, incoming=None):
        self.incoming = list(
            incoming
            or [
                {"type": "hello", "nonce": "nonce-1"},
                {"type": "authenticated", "provider_id": PROVIDER_ID},
            ]
        )
        self.sent = []
        self.closed = False

    async def receive_json(self):
        return self.incoming.pop(0)

    async def send_json(self, payload):
        self.sent.append(payload)

    async def close(self):
        self.closed = True


class StubSession:
    def __init__(self, websocket):
        self.websocket = websocket
        self.closed = False

    async def ws_connect(self, url):
        self.url = url
        return self.websocket

    async def close(self):
        self.closed = True


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
async def test_initialize_connects_authenticates_and_publishes(monkeypatch):
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

    assert session.url == "ws://central/api/v1/discovery/providers"
    assert websocket.sent[0]["type"] == "authenticate"
    assert websocket.sent[1]["type"] == "advertisement.upsert"
    assert websocket.sent[1]["advertisement"]["pricing"]["usd_per_core_month"] == (
        settings.PRICE_USD_PER_CORE_MONTH
    )


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
async def test_initial_connect_failure_is_visible(monkeypatch):
    class FailingSession:
        async def ws_connect(self, url):
            raise RuntimeError("connect failed")

        async def close(self):
            return None

    monkeypatch.setattr(
        "provider.discovery.publishers.aiohttp.ClientSession",
        lambda *args, **kwargs: FailingSession(),
    )
    publisher = CentralDiscoveryPublisher(
        StubResourceTracker({"cpu": 2, "memory": 2, "storage": 10})
    )

    with pytest.raises(RuntimeError, match="connect failed"):
        await publisher.initialize()
