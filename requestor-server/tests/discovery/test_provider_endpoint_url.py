from requestor.config import RequestorConfig
from requestor.provider_client.factory import ProviderClientFactory


def test_provider_client_factory_prefers_advertised_https_endpoint(tmp_path):
    config = RequestorConfig(
        base_dir=tmp_path,
        db_path=tmp_path / "vms.db",
        ssh_key_dir=tmp_path / "ssh",
        environment="production",
    )
    factory = ProviderClientFactory(config)

    client = factory.for_provider_endpoint("203.0.113.10", "https://203.0.113.10")

    assert client.provider_url == "https://203.0.113.10"


def test_provider_url_keeps_legacy_http_fallback(tmp_path):
    config = RequestorConfig(
        base_dir=tmp_path,
        db_path=tmp_path / "vms.db",
        ssh_key_dir=tmp_path / "ssh",
        environment="production",
    )

    assert config.get_provider_url("203.0.113.10") == "http://203.0.113.10:7466"
