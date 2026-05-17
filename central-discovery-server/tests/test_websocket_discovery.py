from datetime import timedelta
from contextlib import contextmanager

import pytest
from eth_account import Account
from eth_account.messages import encode_defunct
from fastapi.testclient import TestClient

from central_discovery.auth import provider_auth_message
from central_discovery.main import app
from central_discovery.time import utc_now


PRIVATE_KEY = "0x" + "11" * 32
PROVIDER_ID = Account.from_key(PRIVATE_KEY).address


@pytest.fixture(autouse=True)
def clear_registry():
    from central_discovery.api.routes import registry

    import asyncio

    asyncio.get_event_loop().run_until_complete(registry.clear())


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_provider_auth_rejects_wrong_signature(client):
    with client.websocket_connect("/api/v1/discovery/providers") as provider:
        hello = provider.receive_json()
        timestamp = utc_now().isoformat()
        provider.send_json(
            {
                "type": "authenticate",
                "provider_id": PROVIDER_ID,
                "nonce": hello["nonce"],
                "timestamp": timestamp,
                "signature": "0x" + "00" * 65,
            }
        )
        error = provider.receive_json()
        assert error["type"] == "error"
        assert "signature" in error["error"]


def test_provider_upsert_snapshot_remove_and_disconnect(client):
    with client.websocket_connect("/api/v1/discovery/requestors") as requestor:
        assert requestor.receive_json()["type"] == "hello"
        requestor.send_json({"type": "subscribe", "filters": {"cpu": 2}})
        snapshot = requestor.receive_json()
        assert snapshot["type"] == "snapshot"
        assert snapshot["advertisements"] == []

        with authenticated_provider(client) as provider:
            provider.send_json(
                {
                    "type": "advertisement.upsert",
                    "advertisement": advertisement(cpu=4, country="SE"),
                }
            )
            accepted = provider.receive_json()
            assert accepted["type"] == "advertisement.accepted"

            update = requestor.receive_json()
            assert update["type"] == "provider.upsert"
            assert update["advertisement"]["provider_id"] == PROVIDER_ID
            assert update["advertisement"]["resources"]["cpu"] == 4

            provider.send_json(
                {
                    "type": "advertisement.upsert",
                    "advertisement": advertisement(cpu=1, country="SE"),
                }
            )
            assert provider.receive_json()["type"] == "advertisement.accepted"
            removed = requestor.receive_json()
            assert removed == {
                "type": "provider.remove",
                "generated_at": removed["generated_at"],
                "provider_id": PROVIDER_ID,
            }

            provider.send_json(
                {
                    "type": "advertisement.upsert",
                    "advertisement": advertisement(cpu=3, country="SE"),
                }
            )
            assert provider.receive_json()["type"] == "advertisement.accepted"
            assert requestor.receive_json()["type"] == "provider.upsert"

        disconnected = requestor.receive_json()
        assert disconnected["type"] == "provider.remove"
        assert disconnected["provider_id"] == PROVIDER_ID


def test_requestor_filter_snapshot_contains_only_matching_connected_providers(client):
    with authenticated_provider(client) as provider:
        provider.send_json(
            {
                "type": "advertisement.upsert",
                "advertisement": advertisement(cpu=2, country="US"),
            }
        )
        assert provider.receive_json()["type"] == "advertisement.accepted"

        with client.websocket_connect("/api/v1/discovery/requestors") as requestor:
            requestor.receive_json()
            requestor.send_json({"type": "subscribe", "filters": {"country": "SE"}})
            assert requestor.receive_json()["advertisements"] == []

            requestor.send_json({"type": "subscribe", "filters": {"country": "US"}})
            snapshot = requestor.receive_json()
            assert len(snapshot["advertisements"]) == 1
            assert snapshot["advertisements"][0]["provider_id"] == PROVIDER_ID


def test_invalid_provider_message_closes_with_error(client):
    with authenticated_provider(client) as provider:
        provider.send_json({"type": "unknown"})
        error = provider.receive_json()
        assert error["type"] == "error"
        assert "unsupported provider message type" in error["error"]


def test_provider_auth_rejects_expired_timestamp(client):
    with client.websocket_connect("/api/v1/discovery/providers") as provider:
        hello = provider.receive_json()
        timestamp = (utc_now() - timedelta(minutes=10)).isoformat()
        provider.send_json(
            {
                "type": "authenticate",
                "provider_id": PROVIDER_ID,
                "nonce": hello["nonce"],
                "timestamp": timestamp,
                "signature": sign_auth(PROVIDER_ID, hello["nonce"], timestamp),
            }
        )
        error = provider.receive_json()
        assert error["type"] == "error"
        assert "expired" in error["error"]


@contextmanager
def authenticated_provider(client):
    with client.websocket_connect("/api/v1/discovery/providers") as provider:
        hello = provider.receive_json()
        timestamp = utc_now().isoformat()
        provider.send_json(
            {
                "type": "authenticate",
                "provider_id": PROVIDER_ID,
                "nonce": hello["nonce"],
                "timestamp": timestamp,
                "signature": sign_auth(PROVIDER_ID, hello["nonce"], timestamp),
            }
        )
        assert provider.receive_json()["type"] == "authenticated"
        yield provider


def sign_auth(provider_id: str, nonce: str, timestamp: str) -> str:
    signed = Account.sign_message(
        encode_defunct(text=provider_auth_message(provider_id, nonce, timestamp)),
        private_key=PRIVATE_KEY,
    )
    return signed.signature.hex()


def advertisement(cpu=2, country="US"):
    return {
        "ip_address": "1.2.3.4",
        "country": country,
        "platform": "arm64",
        "endpoint_protocol": "https",
        "endpoint_host": "provider.example",
        "endpoint_port": 443,
        "endpoint_url": "https://provider.example",
        "resources": {"cpu": cpu, "memory": 4, "storage": 10},
        "pricing": {
            "usd_per_core_month": 6.0,
            "usd_per_gb_ram_month": 2.5,
            "usd_per_gb_storage_month": 0.12,
            "glm_per_core_month": 12.0,
            "glm_per_gb_ram_month": 5.0,
            "glm_per_gb_storage_month": 0.24,
        },
    }
