import asyncio
import types
import pytest

from provider.discovery.advertiser import DiscoveryServerAdvertiser
from provider.discovery.golem_base_advertiser import GolemBaseAdvertiser
from provider.config import settings


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


@pytest.mark.asyncio
async def test_discovery_advertiser_includes_pricing(monkeypatch):
    resources = {"cpu": 2, "memory": 2, "storage": 10}
    rt = StubResourceTracker(resources)
    adv = DiscoveryServerAdvertiser(rt, discovery_url="http://x")
    capture = {}
    adv.session = StubSession(capture)
    # Avoid public IP fetch
    monkeypatch.setattr(adv, "_get_public_ip", lambda: asyncio.sleep(0, result="1.2.3.4"))

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


@pytest.mark.asyncio
async def test_golem_base_advertiser_annotations_include_pricing(monkeypatch):
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
    adv = GolemBaseAdvertiser(rt)
    adv.client = StubClient()
    settings.PUBLIC_IP = "1.2.3.4"

    # Ensure it takes the create path
    from provider.discovery import golem_base_advertiser as gba
    monkeypatch.setattr(gba, "get_provider_entity_keys", lambda *a, **k: asyncio.sleep(0, result=[]))

    # Known pricing
    settings.PRICE_USD_PER_CORE_MONTH = 6.0
    settings.PRICE_USD_PER_GB_RAM_MONTH = 2.5
    settings.PRICE_USD_PER_GB_STORAGE_MONTH = 0.12
    settings.PRICE_GLM_PER_CORE_MONTH = 12.0
    settings.PRICE_GLM_PER_GB_RAM_MONTH = 5.0
    settings.PRICE_GLM_PER_GB_STORAGE_MONTH = 0.24

    await adv.post_advertisement()
    # With updated advertiser, pricing is stored as string annotations
    str_anns = {a.key: a.value for a in getattr(nonlocal_capture, "string_annotations", [])}
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
