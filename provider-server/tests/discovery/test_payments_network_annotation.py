import asyncio
import pytest

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
        return None


@pytest.mark.asyncio
async def test_golem_base_advertiser_includes_payments_network(monkeypatch):
    class StubClient:
        async def disconnect(self):
            pass

        async def create_entities(self, entities):
            nonlocal_capture["string_annotations"] = entities[0].string_annotations
            class R:
                entity_key = "abc"
            return [R()]

    nonlocal_capture = {}
    rt = StubResourceTracker({"cpu": 2, "memory": 2, "storage": 10})
    adv = GolemBaseAdvertiser(rt)
    adv.client = StubClient()
    settings.PUBLIC_IP = "1.2.3.4"
    # Ensure create path
    from provider.discovery import golem_base_advertiser as gba
    monkeypatch.setattr(gba, "get_provider_entity_keys", lambda *a, **k: asyncio.sleep(0, result=[]))

    # Set a known payments profile
    settings.PAYMENTS_NETWORK = "l2.holesky"

    await adv.post_advertisement()
    str_anns = {a.key: a.value for a in nonlocal_capture["string_annotations"]}
    assert str_anns.get("golem_payments_network") == settings.PAYMENTS_NETWORK

