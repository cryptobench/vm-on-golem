import logging

import pytest

from requestor.config import RequestorConfig
from requestor.discovery.domain import ProviderSearchQuery
from requestor.discovery.service import ProviderDiscoveryService
from requestor.provider_client.factory import ProviderClientFactory


def test_provider_client_factory_prefers_advertised_https_endpoint(tmp_path):
    config = RequestorConfig(
        base_dir=tmp_path,
        db_path=tmp_path / "vms.db",
        ssh_key_dir=tmp_path / "ssh",
        environment="production",
    )
    factory = ProviderClientFactory(config)

    client = factory.for_provider_endpoint("https://203.0.113.10")

    assert client.provider_url == "https://203.0.113.10"


def test_provider_url_rejects_http_outside_development(tmp_path):
    config = RequestorConfig(
        base_dir=tmp_path,
        db_path=tmp_path / "vms.db",
        ssh_key_dir=tmp_path / "ssh",
        environment="production",
    )

    with pytest.raises(ValueError):
        config.get_provider_url("203.0.113.10")


@pytest.mark.asyncio
async def test_provider_discovery_logs_backend_and_result_count(tmp_path, caplog):
    class ArkivClient:
        async def close(self):
            pass

        async def find_providers(self, query):
            return []

    class CentralClient:
        session = None

        async def find_providers(self, query):
            return [{"provider_id": "prov1"}]

    caplog.set_level(logging.INFO)
    config = RequestorConfig(
        base_dir=tmp_path,
        db_path=tmp_path / "vms.db",
        ssh_key_dir=tmp_path / "ssh",
        discovery_backend="central",
    )
    service = ProviderDiscoveryService(config, ArkivClient(), CentralClient())

    providers = await service.find_providers(ProviderSearchQuery())

    assert providers == [{"provider_id": "prov1"}]
    assert "Provider discovery completed" in caplog.text
