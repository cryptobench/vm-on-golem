import asyncio
import types
import platform as _plat

import pytest

from provider.discovery.golem_base_advertiser import GolemBaseAdvertiser
from provider.config import settings


class StubResourceTracker:
    def __init__(self, resources, ok=True):
        self._resources = resources
        self._ok = ok

    def get_available_resources(self):
        return self._resources

    def _meets_minimum_requirements(self, resources):
        return bool(self._ok)

    def on_update(self, cb):
        # no-op for tests
        return None


class _Ann:
    def __init__(self, key, value):
        self.key = key
        self.value = value


class _Meta:
    def __init__(self, expires_at_block, string_annotations, numeric_annotations):
        self.expires_at_block = expires_at_block
        self.string_annotations = string_annotations
        self.numeric_annotations = numeric_annotations


def _expected_annotations(resources, ip):
    # Mirror advertiser logic for platform
    raw = (_plat.machine() or '').lower()
    if 'aarch64' in raw or 'arm64' in raw or raw.startswith('arm'):
        platform_str = 'arm64'
    elif 'x86_64' in raw or 'amd64' in raw or 'x64' in raw:
        platform_str = 'x86_64'
    else:
        platform_str = raw or ''

    string_annotations = [
        _Ann("golem_type", "provider"),
        _Ann("golem_network", settings.NETWORK),
        _Ann("golem_payments_network", settings.PAYMENTS_NETWORK),
        _Ann("golem_provider_id", settings.PROVIDER_ID),
        _Ann("golem_ip_address", ip),
        _Ann("golem_country", settings.PROVIDER_COUNTRY),
        _Ann("golem_provider_name", settings.PROVIDER_NAME),
        _Ann("golem_platform", platform_str),
        _Ann("golem_price_currency", "USD/GLM"),
        _Ann("golem_price_usd_core_month", str(float(settings.PRICE_USD_PER_CORE_MONTH))),
        _Ann("golem_price_usd_ram_gb_month", str(float(settings.PRICE_USD_PER_GB_RAM_MONTH))),
        _Ann("golem_price_usd_storage_gb_month", str(float(settings.PRICE_USD_PER_GB_STORAGE_MONTH))),
        _Ann("golem_price_glm_core_month", str(float(settings.PRICE_GLM_PER_CORE_MONTH))),
        _Ann("golem_price_glm_ram_gb_month", str(float(settings.PRICE_GLM_PER_GB_RAM_MONTH))),
        _Ann("golem_price_glm_storage_gb_month", str(float(settings.PRICE_GLM_PER_GB_STORAGE_MONTH))),
    ]
    numeric_annotations = [
        _Ann("golem_cpu", resources["cpu"]),
        _Ann("golem_memory", resources["memory"]),
        _Ann("golem_storage", resources["storage"]),
    ]
    return string_annotations, numeric_annotations


class StubClient:
    def __init__(self):
        self.created = []
        self.updated = []
        self.deleted = []
        self.extended = []
        self._meta = {}
        self._block_number = 0

    async def disconnect(self):
        pass

    async def create_entities(self, entities):
        self.created.extend(entities)
        # Return receipts with fake keys
        class R:
            def __init__(self, key):
                self.entity_key = key

        return [R(f"key-{len(self.created)}")]  # type: ignore[no-any-return]

    async def update_entities(self, updates):
        self.updated.extend(updates)
        return []

    async def delete_entities(self, deletes):
        self.deleted.extend(deletes)
        return []

    async def extend_entities(self, extensions):
        self.extended.extend(extensions)
        return []

    async def get_entity_metadata(self, entity_key):
        return self._meta[entity_key]

    def set_metadata(self, entity_key, meta):
        self._meta[entity_key] = meta

    class _Eth:
        def __init__(self, parent):
            self._parent = parent

        async def get_block_number(self):
            return self._parent._block_number

    class _HTTP:
        def __init__(self, parent):
            self.eth = StubClient._Eth(parent)

    def http_client(self):
        return StubClient._HTTP(self)


@pytest.mark.asyncio
async def test_create_when_no_existing(monkeypatch):
    rt = StubResourceTracker({"cpu": 2, "memory": 2, "storage": 10})
    adv = GolemBaseAdvertiser(rt)
    client = StubClient()
    adv.client = client
    settings.PUBLIC_IP = "1.2.3.4"

    # No existing keys
    from provider.discovery import golem_base_advertiser as gba
    monkeypatch.setattr(gba, "get_provider_entity_keys", lambda *a, **k: asyncio.sleep(0, result=[]))

    # Configure interval to a known value
    settings.GOLEM_BASE_ADVERTISEMENT_INTERVAL = 360
    await adv.post_advertisement()

    assert len(client.created) == 1
    assert client.created[0].btl == 720  # 360s * 2 blocks/sec


@pytest.mark.asyncio
async def test_delete_when_multiple_and_recreate(monkeypatch):
    rt = StubResourceTracker({"cpu": 2, "memory": 2, "storage": 10})
    adv = GolemBaseAdvertiser(rt)
    client = StubClient()
    adv.client = client
    settings.PUBLIC_IP = "1.2.3.4"

    from provider.discovery import golem_base_advertiser as gba
    monkeypatch.setattr(
        gba,
        "get_provider_entity_keys",
        lambda *a, **k: asyncio.sleep(0, result=["k1", "k2"]),
    )

    settings.GOLEM_BASE_ADVERTISEMENT_INTERVAL = 100
    await adv.post_advertisement()

    assert len(client.deleted) == 2
    assert len(client.created) == 1
    assert client.created[0].btl == 200


@pytest.mark.asyncio
async def test_update_when_annotations_differ(monkeypatch):
    rt = StubResourceTracker({"cpu": 4, "memory": 4, "storage": 20})
    adv = GolemBaseAdvertiser(rt)
    client = StubClient()
    adv.client = client
    settings.PUBLIC_IP = "1.2.3.4"

    # One existing key
    key = "ekey"
    from provider.discovery import golem_base_advertiser as gba
    monkeypatch.setattr(gba, "get_provider_entity_keys", lambda *a, **k: asyncio.sleep(0, result=[key]))

    # Current metadata deliberately mismatched (empty annotations)
    client.set_metadata(key, _Meta(expires_at_block=9999999, string_annotations=[], numeric_annotations=[]))

    settings.GOLEM_BASE_ADVERTISEMENT_INTERVAL = 50
    await adv.post_advertisement()

    assert len(client.updated) == 1
    assert client.updated[0].btl == 100


@pytest.mark.asyncio
async def test_extend_when_up_to_date_and_near_expiry(monkeypatch):
    res = {"cpu": 2, "memory": 2, "storage": 10}
    rt = StubResourceTracker(res)
    adv = GolemBaseAdvertiser(rt)
    client = StubClient()
    adv.client = client
    settings.PUBLIC_IP = "1.2.3.4"

    key = "ekey"
    from provider.discovery import golem_base_advertiser as gba
    monkeypatch.setattr(gba, "get_provider_entity_keys", lambda *a, **k: asyncio.sleep(0, result=[key]))

    # Make metadata annotations equal to expected
    s_anns, n_anns = _expected_annotations(res, settings.PUBLIC_IP)

    desired_interval = 50
    settings.GOLEM_BASE_ADVERTISEMENT_INTERVAL = desired_interval
    desired_btl = desired_interval * 2

    # Set current block and expiry to be below refresh threshold (<= 20% of btl)
    client._block_number = 1000
    refresh_threshold = max(10, desired_btl // 5)
    expires_at = client._block_number + (refresh_threshold - 1)
    client.set_metadata(key, _Meta(expires_at_block=expires_at, string_annotations=s_anns, numeric_annotations=n_anns))

    await adv.post_advertisement()

    assert len(client.extended) == 1
    assert client.extended[0].number_of_blocks == desired_btl
    assert len(client.updated) == 0


@pytest.mark.asyncio
async def test_no_extend_when_ttl_sufficient(monkeypatch):
    res = {"cpu": 2, "memory": 2, "storage": 10}
    rt = StubResourceTracker(res)
    adv = GolemBaseAdvertiser(rt)
    client = StubClient()
    adv.client = client
    settings.PUBLIC_IP = "1.2.3.4"

    key = "ekey"
    from provider.discovery import golem_base_advertiser as gba
    monkeypatch.setattr(gba, "get_provider_entity_keys", lambda *a, **k: asyncio.sleep(0, result=[key]))

    s_anns, n_anns = _expected_annotations(res, settings.PUBLIC_IP)

    desired_interval = 50
    settings.GOLEM_BASE_ADVERTISEMENT_INTERVAL = desired_interval
    desired_btl = desired_interval * 2

    client._block_number = 2000
    refresh_threshold = max(10, desired_btl // 5)
    expires_at = client._block_number + (refresh_threshold + 5)
    client.set_metadata(key, _Meta(expires_at_block=expires_at, string_annotations=s_anns, numeric_annotations=n_anns))

    await adv.post_advertisement()

    assert len(client.extended) == 0
    assert len(client.updated) == 0
    assert len(client.created) == 0


@pytest.mark.asyncio
async def test_skip_when_resources_low(monkeypatch):
    rt = StubResourceTracker({"cpu": 0, "memory": 0, "storage": 0}, ok=False)
    adv = GolemBaseAdvertiser(rt)
    client = StubClient()
    adv.client = client
    settings.PUBLIC_IP = "1.2.3.4"

    from provider.discovery import golem_base_advertiser as gba
    monkeypatch.setattr(gba, "get_provider_entity_keys", lambda *a, **k: asyncio.sleep(0, result=[]))

    await adv.post_advertisement()
    assert not client.created and not client.updated and not client.deleted and not client.extended


@pytest.mark.asyncio
async def test_skip_when_no_public_ip(monkeypatch):
    rt = StubResourceTracker({"cpu": 2, "memory": 2, "storage": 10})
    adv = GolemBaseAdvertiser(rt)
    client = StubClient()
    adv.client = client
    settings.PUBLIC_IP = None

    from provider.discovery import golem_base_advertiser as gba
    monkeypatch.setattr(gba, "get_provider_entity_keys", lambda *a, **k: asyncio.sleep(0, result=[]))

    await adv.post_advertisement()
    assert not client.created and not client.updated and not client.deleted and not client.extended

