import asyncio
import logging
import types

import pytest

from provider.config import settings
from provider.discovery.arkiv_publisher import ArkivDiscoveryPublisher
from provider.discovery.publishers import CentralDiscoveryPublisher


class StubResourceTracker:
    def __init__(self, resources):
        self._resources = resources

    def get_available_resources(self):
        return self._resources

    def _meets_minimum_requirements(self, resources):
        return True

    def on_update(self, cb):
        # no-op for tests
        return None


class StubResponse:
    def __init__(self):
        self.ok = True
        self._text = "ok"

    async def text(self):
        return self._text

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class StubSession:
    def __init__(self, capture):
        self.capture = capture

    def post(self, url, headers=None, json=None, timeout=None):
        # capture payload
        self.capture["url"] = url
        self.capture["json"] = json
        return StubResponse()

    async def close(self):
        pass


class StubCertificateService:
    def __init__(self, advertisable):
        self.advertisable = advertisable

    def endpoint_is_advertisable(self):
        return self.advertisable


@pytest.mark.asyncio
async def test_central_publisher_includes_pricing(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    resources = {"cpu": 2, "memory": 2, "storage": 10}
    rt = StubResourceTracker(resources)
    adv = CentralDiscoveryPublisher(rt, discovery_url="http://x")
    capture = {}
    adv.session = StubSession(capture)
    # Avoid public IP fetch
    monkeypatch.setattr(
        adv, "_get_public_ip", lambda: asyncio.sleep(0, result="1.2.3.4")
    )

    # Known pricing
    settings.PRICE_USD_PER_CORE_MONTH = 6.0
    settings.PRICE_USD_PER_GB_RAM_MONTH = 2.5
    settings.PRICE_USD_PER_GB_STORAGE_MONTH = 0.12
    settings.PRICE_GLM_PER_CORE_MONTH = 12.0
    settings.PRICE_GLM_PER_GB_RAM_MONTH = 5.0
    settings.PRICE_GLM_PER_GB_STORAGE_MONTH = 0.24

    await adv.post_advertisement()
    payload = capture["json"]
    assert payload["pricing"]["usd_per_core_month"] == 6.0
    assert payload["pricing"]["glm_per_gb_ram_month"] == 5.0
    assert "Posted central discovery advertisement" in caplog.text


@pytest.mark.asyncio
async def test_central_publisher_uses_configured_public_ip(monkeypatch):
    rt = StubResourceTracker({"cpu": 2, "memory": 2, "storage": 10})
    adv = CentralDiscoveryPublisher(rt, discovery_url="http://x")
    capture = {}
    adv.session = StubSession(capture)
    monkeypatch.setattr(settings, "PUBLIC_IP", "127.0.0.1")

    async def fail_public_ip_lookup():
        raise AssertionError("public IP lookup should not be called")

    monkeypatch.setattr(adv, "_get_public_ip", fail_public_ip_lookup)

    await adv.post_advertisement()

    assert capture["json"]["ip_address"] == "127.0.0.1"


@pytest.mark.asyncio
async def test_central_publisher_skips_when_certificate_is_not_usable(
    monkeypatch, caplog
):
    caplog.set_level(logging.WARNING)
    rt = StubResourceTracker({"cpu": 2, "memory": 2, "storage": 10})
    adv = CentralDiscoveryPublisher(
        rt,
        discovery_url="http://x",
        certificate_service=StubCertificateService(False),
    )
    capture = {}
    adv.session = StubSession(capture)
    monkeypatch.setattr(settings, "PUBLIC_IP", "127.0.0.1")

    await adv.post_advertisement()

    assert capture == {}
    assert "Skipping central discovery advertisement" in caplog.text


@pytest.mark.asyncio
async def test_arkiv_publisher_annotations_include_pricing(monkeypatch):
    # Stub client to capture created entity
    class StubClient:
        async def disconnect(self):
            pass

        async def create_entities(self, entities):
            # capture annotations of first entity
            nonlocal_capture["numeric_annotations"] = entities[0].numeric_annotations
            nonlocal_capture["string_annotations"] = entities[0].string_annotations
            # Return fake receipt
            class R:
                entity_key = "abc"

            return [R()]

    nonlocal_capture = {}
    rt = StubResourceTracker({"cpu": 2, "memory": 2, "storage": 10})
    adv = ArkivDiscoveryPublisher(rt)
    adv.client = StubClient()
    settings.PUBLIC_IP = "1.2.3.4"

    # Ensure it takes the create path
    from provider.discovery import arkiv_publisher

    monkeypatch.setattr(
        arkiv_publisher,
        "get_provider_entity_keys",
        lambda *a, **k: asyncio.sleep(0, result=[]),
    )

    # Known pricing
    settings.PRICE_USD_PER_CORE_MONTH = 6.0
    settings.PRICE_USD_PER_GB_RAM_MONTH = 2.5
    settings.PRICE_USD_PER_GB_STORAGE_MONTH = 0.12
    settings.PRICE_GLM_PER_CORE_MONTH = 12.0
    settings.PRICE_GLM_PER_GB_RAM_MONTH = 5.0
    settings.PRICE_GLM_PER_GB_STORAGE_MONTH = 0.24

    await adv.post_advertisement()
    # Arkiv stores pricing as string annotations.
    str_anns = {
        a.key: a.value for a in getattr(nonlocal_capture, "string_annotations", [])
    }
    # Older StubClient only captured numeric_annotations; adapt to capture both
    if not str_anns and "string_annotations" in nonlocal_capture:
        str_anns = {a.key: a.value for a in nonlocal_capture["string_annotations"]}
    num_anns = {a.key: a.value for a in nonlocal_capture["numeric_annotations"]}
    # Pricing as strings
    assert str_anns["golem_price_usd_core_month"] == str(6.0)
    assert str_anns["golem_price_glm_ram_gb_month"] == str(5.0)
    # Resources remain numeric ints
    assert num_anns["golem_cpu"] == 2
    assert num_anns["golem_memory"] == 2
    assert num_anns["golem_storage"] == 10


@pytest.mark.asyncio
async def test_arkiv_publisher_skips_when_certificate_is_not_usable(monkeypatch):
    class StubClient:
        async def disconnect(self):
            pass

    rt = StubResourceTracker({"cpu": 2, "memory": 2, "storage": 10})
    adv = ArkivDiscoveryPublisher(rt, certificate_service=StubCertificateService(False))
    adv.client = StubClient()
    settings.PUBLIC_IP = "1.2.3.4"

    from provider.discovery import arkiv_publisher

    async def fail_lookup(*_args, **_kwargs):
        raise AssertionError("advertisement lookup should not run")

    monkeypatch.setattr(arkiv_publisher, "get_provider_entity_keys", fail_lookup)

    await adv.post_advertisement()
