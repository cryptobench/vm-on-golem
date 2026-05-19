import pytest
from pydantic import ValidationError

from provider.config import (
    Settings,
    derive_port_check_url,
    _development_public_ip,
    normalize_acme_env,
)


def _set_settings_paths(monkeypatch, tmp_path):
    monkeypatch.setenv("GOLEM_PROVIDER_VM_DATA_DIR", str(tmp_path / "vms"))
    monkeypatch.setenv("GOLEM_PROVIDER_SSH_KEY_DIR", str(tmp_path / "ssh"))
    monkeypatch.setenv("GOLEM_PROVIDER_CLOUD_INIT_DIR", str(tmp_path / "cloud-init"))
    monkeypatch.setenv("GOLEM_PROVIDER_PROXY_STATE_DIR", str(tmp_path / "proxy"))
    monkeypatch.setenv("GOLEM_PROVIDER_CERT_DIR", str(tmp_path / "certs"))


def test_discovery_ws_url_has_central_websocket_default(monkeypatch, tmp_path):
    monkeypatch.delenv("GOLEM_PROVIDER_DISCOVERY_WS_URL", raising=False)
    _set_settings_paths(monkeypatch, tmp_path)

    settings = Settings()

    assert (
        settings.DISCOVERY_WS_URL
        == "wss://78.46.172.104/api/v1/discovery/providers"
    )


def test_discovery_ws_url_override_wins(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "GOLEM_PROVIDER_DISCOVERY_WS_URL",
        "ws://127.0.0.1:9001/api/v1/discovery/providers",
    )
    _set_settings_paths(monkeypatch, tmp_path)

    settings = Settings()

    assert settings.DISCOVERY_WS_URL == "ws://127.0.0.1:9001/api/v1/discovery/providers"


def test_port_check_url_defaults_to_discovery_http_origin(monkeypatch, tmp_path):
    monkeypatch.delenv("GOLEM_PROVIDER_PORT_CHECK_TLS_URL", raising=False)
    monkeypatch.setenv(
        "GOLEM_PROVIDER_DISCOVERY_WS_URL",
        "ws://127.0.0.1:9001/api/v1/discovery/providers",
    )
    _set_settings_paths(monkeypatch, tmp_path)

    settings = Settings()

    assert settings.PORT_CHECK_TLS_URL == "http://127.0.0.1:9001"


def test_port_check_url_defaults_to_discovery_https_origin(monkeypatch, tmp_path):
    monkeypatch.delenv("GOLEM_PROVIDER_PORT_CHECK_TLS_URL", raising=False)
    monkeypatch.setenv(
        "GOLEM_PROVIDER_DISCOVERY_WS_URL",
        "wss://central.example.test/api/v1/discovery/providers",
    )
    _set_settings_paths(monkeypatch, tmp_path)

    settings = Settings()

    assert settings.PORT_CHECK_TLS_URL == "https://central.example.test"


def test_port_check_url_override_wins(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "GOLEM_PROVIDER_DISCOVERY_WS_URL",
        "wss://central.example.test/api/v1/discovery/providers",
    )
    monkeypatch.setenv("GOLEM_PROVIDER_PORT_CHECK_TLS_URL", "https://checks.example")
    _set_settings_paths(monkeypatch, tmp_path)

    settings = Settings()

    assert settings.PORT_CHECK_TLS_URL == "https://checks.example"


def test_derive_port_check_url_rejects_non_websocket_url():
    with pytest.raises(ValueError):
        derive_port_check_url("https://central.example.test")


def test_acme_env_normalization_accepts_prod_alias():
    assert normalize_acme_env("prod") == "production"


def test_acme_staging_env_selects_staging_directory(monkeypatch, tmp_path):
    monkeypatch.delenv("GOLEM_PROVIDER_ACME_DIRECTORY_URL", raising=False)
    monkeypatch.setenv("GOLEM_PROVIDER_ACME_ENV", "staging")
    _set_settings_paths(monkeypatch, tmp_path)

    settings = Settings()

    assert (
        settings.ACME_DIRECTORY_URL
        == "https://acme-staging-v02.api.letsencrypt.org/directory"
    )
    assert settings.ACME_ENV == "staging"


def test_acme_production_env_selects_production_directory(monkeypatch, tmp_path):
    monkeypatch.delenv("GOLEM_PROVIDER_ACME_DIRECTORY_URL", raising=False)
    monkeypatch.setenv("GOLEM_PROVIDER_ACME_ENV", "production")
    _set_settings_paths(monkeypatch, tmp_path)

    settings = Settings()

    assert (
        settings.ACME_DIRECTORY_URL == "https://acme-v02.api.letsencrypt.org/directory"
    )
    assert settings.ACME_ENV == "production"


def test_acme_prod_alias_selects_production_directory(monkeypatch, tmp_path):
    monkeypatch.delenv("GOLEM_PROVIDER_ACME_DIRECTORY_URL", raising=False)
    monkeypatch.setenv("GOLEM_PROVIDER_ACME_ENV", "prod")
    _set_settings_paths(monkeypatch, tmp_path)

    settings = Settings()

    assert (
        settings.ACME_DIRECTORY_URL == "https://acme-v02.api.letsencrypt.org/directory"
    )
    assert settings.ACME_ENV == "production"


def test_acme_directory_url_override_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("GOLEM_PROVIDER_ACME_ENV", "staging")
    monkeypatch.setenv(
        "GOLEM_PROVIDER_ACME_DIRECTORY_URL",
        "https://acme.example.test/directory",
    )
    _set_settings_paths(monkeypatch, tmp_path)

    settings = Settings()

    assert settings.ACME_DIRECTORY_URL == "https://acme.example.test/directory"


def test_acme_invalid_env_fails(monkeypatch, tmp_path):
    monkeypatch.delenv("GOLEM_PROVIDER_ACME_DIRECTORY_URL", raising=False)
    monkeypatch.setenv("GOLEM_PROVIDER_ACME_ENV", "qa")
    _set_settings_paths(monkeypatch, tmp_path)

    with pytest.raises(ValidationError, match="ACME environment"):
        Settings()


def test_development_public_ip_prefers_default_route(monkeypatch):
    class RouteSocket:
        def connect(self, target):
            assert target == ("8.8.8.8", 80)

        def getsockname(self):
            return ("192.168.50.48", 49152)

        def close(self):
            pass

    monkeypatch.setattr("provider.config.socket.socket", lambda *args: RouteSocket())
    monkeypatch.setattr("provider.config.socket.gethostname", lambda: "provider-host")
    monkeypatch.setattr(
        "provider.config.socket.gethostbyname_ex",
        lambda hostname: (hostname, [], ["192.168.2.1"]),
    )

    assert _development_public_ip() == "192.168.50.48"


def test_development_public_ip_falls_back_to_hostname(monkeypatch):
    class UnroutableSocket:
        def connect(self, target):
            raise OSError("no route")

        def close(self):
            pass

    monkeypatch.setattr(
        "provider.config.socket.socket", lambda *args: UnroutableSocket()
    )
    monkeypatch.setattr("provider.config.socket.gethostname", lambda: "provider-host")
    monkeypatch.setattr(
        "provider.config.socket.gethostbyname_ex",
        lambda hostname: (hostname, [], ["127.0.0.1", "192.168.2.1"]),
    )

    assert _development_public_ip() == "192.168.2.1"


def test_public_endpoint_internal_ports_match_public_defaults(monkeypatch, tmp_path):
    monkeypatch.delenv("GOLEM_PROVIDER_ACME_HTTP_PUBLIC_PORT", raising=False)
    monkeypatch.delenv("GOLEM_PROVIDER_ACME_HTTP_INTERNAL_PORT", raising=False)
    monkeypatch.delenv("GOLEM_PROVIDER_PUBLIC_HTTPS_PORT", raising=False)
    monkeypatch.delenv("GOLEM_PROVIDER_PUBLIC_HTTPS_INTERNAL_PORT", raising=False)
    _set_settings_paths(monkeypatch, tmp_path)

    settings = Settings()

    assert settings.ACME_HTTP_PUBLIC_PORT == 80
    assert settings.ACME_HTTP_INTERNAL_PORT == 80
    assert settings.PUBLIC_HTTPS_PORT == 443
    assert settings.PUBLIC_HTTPS_INTERNAL_PORT == 443


def test_hoodi_payments_profile_defaults_to_l1_rpc_and_ws(monkeypatch, tmp_path):
    monkeypatch.delenv("GOLEM_PROVIDER_PAYMENTS_RPC_URL", raising=False)
    monkeypatch.delenv("GOLEM_PROVIDER_PAYMENTS_WS_URL", raising=False)
    monkeypatch.setenv("GOLEM_PROVIDER_PAYMENTS_NETWORK", "hoodi")
    _set_settings_paths(monkeypatch, tmp_path)

    settings = Settings()

    assert settings.PAYMENTS_RPC_URL == "https://rpc.hoodi.ethpandaops.io"
    assert settings.PAYMENTS_WS_URL == "wss://ethereum-hoodi-rpc.publicnode.com"


def test_legacy_payment_rpc_aliases_are_ignored(monkeypatch, tmp_path):
    monkeypatch.delenv("GOLEM_PROVIDER_PAYMENTS_RPC_URL", raising=False)
    monkeypatch.setenv("GOLEM_PROVIDER_PAYMENTS_NETWORK", "hoodi")
    monkeypatch.setenv("GOLEM_PROVIDER_L2_RPC_URL", "http://legacy-l2.invalid")
    monkeypatch.setenv("GOLEM_PROVIDER_KAOLIN_RPC_URL", "http://legacy-kaolin.invalid")
    _set_settings_paths(monkeypatch, tmp_path)

    settings = Settings()

    assert settings.PAYMENTS_RPC_URL == "https://rpc.hoodi.ethpandaops.io"


def test_explicit_payments_rpc_and_ws_win(monkeypatch, tmp_path):
    monkeypatch.setenv("GOLEM_PROVIDER_PAYMENTS_RPC_URL", "https://rpc.example")
    monkeypatch.setenv("GOLEM_PROVIDER_PAYMENTS_WS_URL", "wss://ws.example")
    _set_settings_paths(monkeypatch, tmp_path)

    settings = Settings()

    assert settings.PAYMENTS_RPC_URL == "https://rpc.example"
    assert settings.PAYMENTS_WS_URL == "wss://ws.example"
