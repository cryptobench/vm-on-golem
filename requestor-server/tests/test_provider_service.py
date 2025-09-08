from pathlib import Path
import sys
import types
from types import SimpleNamespace

sys.path.append(str(Path(__file__).resolve().parents[1]))

import pytest


@pytest.fixture(autouse=True)
def stub_golem_base_sdk(monkeypatch):
    class DummyClient:
        @classmethod
        async def create(cls, *args, **kwargs):
            return cls()
        async def disconnect(self):
            pass
        def http_client(self):
            class HC:
                class eth:
                    async def get_block(self, arg):
                        return SimpleNamespace(number=0)
            return HC()
    types_mod = types.ModuleType("golem_base_sdk.types")
    types_mod.EntityKey = object
    class GB:
        @staticmethod
        def from_hex_string(s):
            return s
    types_mod.GenericBytes = GB
    sdk_mod = types.ModuleType("golem_base_sdk")
    sdk_mod.GolemBaseClient = DummyClient
    sdk_mod.types = types_mod
    monkeypatch.setitem(sys.modules, "golem_base_sdk", sdk_mod)
    monkeypatch.setitem(sys.modules, "golem_base_sdk.types", types_mod)

    yield

    sys.modules.pop("golem_base_sdk", None)
    sys.modules.pop("golem_base_sdk.types", None)

from requestor.services.provider_service import ProviderService
from requestor.errors import ProviderError
import click


def test_provider_headers():
    svc = ProviderService()
    assert "Provider ID" in svc.provider_headers


@pytest.mark.asyncio
async def test_format_provider_row(monkeypatch):
    provider = {
        "provider_id": "pid",
        "provider_name": "name",
        "ip_address": "1.2.3.4",
        "country": "PL",
        "resources": {"cpu": 2, "memory": 4, "storage": 10},
        "created_at_block": 0,
    }
    monkeypatch.setattr(click, "style", lambda x, **k: x)
    svc = ProviderService()
    row = await svc.format_provider_row(provider, colorize=True)
    assert row[0] == "pid"
    assert row[-1] == "N/A"


@pytest.mark.asyncio
async def test_check_resource_availability_false(monkeypatch):
    svc = ProviderService()
    async def fake_get(pid):
        return {"cpu": 1, "memory": 1, "storage": 1}
    monkeypatch.setattr(svc, "get_provider_resources", fake_get)
    ok = await svc.check_resource_availability("p", 2, 2, 2)
    assert ok is False


@pytest.mark.asyncio
async def test_verify_provider_missing(monkeypatch):
    svc = ProviderService()
    async def fake_find(*a, **k):
        return [{"provider_id": "a"}]
    monkeypatch.setattr(svc, "find_providers", fake_find)
    with pytest.raises(ProviderError):
        await svc.verify_provider("b")
