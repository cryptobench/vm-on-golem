from provider.config import Settings, normalize_discovery_backend


def test_discovery_backend_defaults_to_central(monkeypatch, tmp_path):
    monkeypatch.delenv("GOLEM_PROVIDER_DISCOVERY_BACKEND", raising=False)
    monkeypatch.setenv("GOLEM_PROVIDER_VM_DATA_DIR", str(tmp_path / "vms"))
    monkeypatch.setenv("GOLEM_PROVIDER_SSH_KEY_DIR", str(tmp_path / "ssh"))
    monkeypatch.setenv("GOLEM_PROVIDER_CLOUD_INIT_DIR", str(tmp_path / "cloud-init"))
    monkeypatch.setenv("GOLEM_PROVIDER_PROXY_STATE_DIR", str(tmp_path / "proxy"))

    settings = Settings()

    assert settings.DISCOVERY_BACKEND == "central"


def test_empty_discovery_backend_normalizes_to_central():
    assert normalize_discovery_backend("") == "central"
