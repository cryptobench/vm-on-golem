import pytest
from pydantic import ValidationError

from provider.config import Settings, normalize_acme_env, normalize_discovery_backend


def _set_settings_paths(monkeypatch, tmp_path):
    monkeypatch.setenv("GOLEM_PROVIDER_VM_DATA_DIR", str(tmp_path / "vms"))
    monkeypatch.setenv("GOLEM_PROVIDER_SSH_KEY_DIR", str(tmp_path / "ssh"))
    monkeypatch.setenv("GOLEM_PROVIDER_CLOUD_INIT_DIR", str(tmp_path / "cloud-init"))
    monkeypatch.setenv("GOLEM_PROVIDER_PROXY_STATE_DIR", str(tmp_path / "proxy"))
    monkeypatch.setenv("GOLEM_PROVIDER_CERT_DIR", str(tmp_path / "certs"))


def test_discovery_backend_defaults_to_central(monkeypatch, tmp_path):
    monkeypatch.delenv("GOLEM_PROVIDER_DISCOVERY_BACKEND", raising=False)
    _set_settings_paths(monkeypatch, tmp_path)

    settings = Settings()

    assert settings.DISCOVERY_BACKEND == "central"


def test_empty_discovery_backend_normalizes_to_central():
    assert normalize_discovery_backend("") == "central"


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
