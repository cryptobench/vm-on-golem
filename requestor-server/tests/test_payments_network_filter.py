import sys
import types
import pytest

from requestor.services.provider_service import ProviderService
from requestor.config import config


@pytest.mark.asyncio
async def test_query_includes_payments_network_by_default(monkeypatch):
    class DummyClient:
        last_query = None
        @classmethod
        async def create(cls, *args, **kwargs):
            return cls()
        async def disconnect(self):
            pass
        async def query_entities(self, q):
            type(self).last_query = q
            class E:
                entity_key = "0xabc"
            return [E()]
        async def get_entity_metadata(self, entity_key):
            class Ann:
                def __init__(self, k, v):
                    self.key, self.value = k, v
            class M:
                string_annotations = [
                    Ann("golem_type", "provider"),
                    Ann("golem_network", config.network),
                    Ann("golem_payments_network", config.payments_network),
                    Ann("golem_provider_id", "0xprov"),
                    Ann("golem_ip_address", "1.2.3.4"),
                    Ann("golem_country", "SE"),
                    Ann("golem_provider_name", "prov"),
                    Ann("golem_price_usd_core_month", "6.0"),
                    Ann("golem_price_usd_ram_gb_month", "2.5"),
                    Ann("golem_price_usd_storage_gb_month", "0.1"),
                ]
                numeric_annotations = [Ann("golem_cpu", 2), Ann("golem_memory", 4), Ann("golem_storage", 10)]
                expires_at_block = 200
            return M()

    # Stub SDK module
    sdk_mod = types.ModuleType("golem_base_sdk")
    sdk_mod.GolemBaseClient = DummyClient
    types_mod = types.ModuleType("golem_base_sdk.types")
    class GB:
        @staticmethod
        def from_hex_string(x):
            return x
    types_mod.GenericBytes = GB
    class EK:
        def __init__(self, x):
            self.x = x
    types_mod.EntityKey = EK
    monkeypatch.setitem(sys.modules, "golem_base_sdk", sdk_mod)
    monkeypatch.setitem(sys.modules, "golem_base_sdk.types", types_mod)
    # Ensure the ProviderService module sees our stubs
    from requestor.services import provider_service as ps
    monkeypatch.setattr(ps, "GolemBaseClient", DummyClient)
    monkeypatch.setattr(ps, "GenericBytes", GB)
    monkeypatch.setattr(ps, "EntityKey", EK)

    # Ensure known config
    config.network = "testnet"
    config.payments_network = "l2.holesky"

    svc = ProviderService()
    async with svc:
        providers = await svc.find_providers(driver="golem-base")
    # Query should include both network filters
    assert 'golem_network="testnet"' in DummyClient.last_query
    assert 'golem_payments_network="l2.holesky"' in DummyClient.last_query
    # Return should include parsed provider
    assert providers and providers[0]["payments_network"] == "l2.holesky"


@pytest.mark.asyncio
async def test_query_omits_payments_filter_when_all_flag(monkeypatch):
    class DummyClient:
        last_query = None
        @classmethod
        async def create(cls, *args, **kwargs):
            return cls()
        async def disconnect(self):
            pass
        async def query_entities(self, q):
            type(self).last_query = q
            class E:
                entity_key = "0xabc"
            return [E()]
        async def get_entity_metadata(self, entity_key):
            class Ann:
                def __init__(self, k, v):
                    self.key, self.value = k, v
            class M:
                string_annotations = [Ann("golem_provider_id", "0xprov")]
                numeric_annotations = [Ann("golem_cpu", 2), Ann("golem_memory", 4), Ann("golem_storage", 10)]
                expires_at_block = 200
            return M()

    sdk_mod = types.ModuleType("golem_base_sdk")
    sdk_mod.GolemBaseClient = DummyClient
    types_mod = types.ModuleType("golem_base_sdk.types")
    class GB:
        @staticmethod
        def from_hex_string(x):
            return x
    types_mod.GenericBytes = GB
    class EK:
        def __init__(self, x):
            self.x = x
    types_mod.EntityKey = EK
    monkeypatch.setitem(sys.modules, "golem_base_sdk", sdk_mod)
    monkeypatch.setitem(sys.modules, "golem_base_sdk.types", types_mod)
    from requestor.services import provider_service as ps
    monkeypatch.setattr(ps, "GolemBaseClient", DummyClient)
    monkeypatch.setattr(ps, "GenericBytes", GB)
    monkeypatch.setattr(ps, "EntityKey", EK)

    config.network = "testnet"
    config.payments_network = "l2.holesky"
    svc = ProviderService()
    async with svc:
        await svc.find_providers(driver="golem-base", include_all_payments=True)
    assert 'golem_payments_network=' not in (DummyClient.last_query or '')


@pytest.mark.asyncio
async def test_query_overrides_payments_network(monkeypatch):
    class DummyClient:
        last_query = None
        @classmethod
        async def create(cls, *args, **kwargs):
            return cls()
        async def disconnect(self):
            pass
        async def query_entities(self, q):
            type(self).last_query = q
            return []
        async def get_entity_metadata(self, entity_key):
            raise AssertionError("should not be called")

    sdk_mod = types.ModuleType("golem_base_sdk")
    sdk_mod.GolemBaseClient = DummyClient
    types_mod = types.ModuleType("golem_base_sdk.types")
    class GB:
        @staticmethod
        def from_hex_string(x):
            return x
    types_mod.GenericBytes = GB
    class EK:
        def __init__(self, x):
            self.x = x
    types_mod.EntityKey = EK
    monkeypatch.setitem(sys.modules, "golem_base_sdk", sdk_mod)
    monkeypatch.setitem(sys.modules, "golem_base_sdk.types", types_mod)
    from requestor.services import provider_service as ps
    monkeypatch.setattr(ps, "GolemBaseClient", DummyClient)
    monkeypatch.setattr(ps, "GenericBytes", GB)
    monkeypatch.setattr(ps, "EntityKey", EK)

    svc = ProviderService()
    async with svc:
        await svc.find_providers(driver="golem-base", payments_network="kaolin.holesky")
    assert 'golem_payments_network="kaolin.holesky"' in (DummyClient.last_query or '')
