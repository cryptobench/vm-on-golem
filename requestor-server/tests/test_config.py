from pathlib import Path
import pytest
import sys
sys.path.append(str(Path(__file__).resolve().parents[1]))

from requestor.config import RequestorConfig


def test_default_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    cfg = RequestorConfig()
    expected_base = tmp_path / ".golem"
    assert cfg.base_dir == expected_base
    assert cfg.ssh_key_dir == expected_base / "ssh"
    assert cfg.db_path == expected_base / "vms.db"


def test_dev_mode_env(monkeypatch):
    monkeypatch.setenv("golem_dev_mode", "true")
    cfg = RequestorConfig()
    assert cfg.environment == "development"
    assert cfg.DEV_MODE is True


def test_discovery_url_dev_mode():
    cfg = RequestorConfig(environment="development")
    assert cfg.discovery_url.startswith("DEVMODE-")


def test_get_provider_url():
    cfg = RequestorConfig()
    assert cfg.get_provider_url("127.0.0.1") == "http://127.0.0.1:7466"


def test_custom_base_dir(tmp_path):
    cfg = RequestorConfig(base_dir=tmp_path)
    assert cfg.ssh_key_dir == tmp_path / "ssh"
    assert cfg.db_path == tmp_path / "vms.db"


def test_force_localhost_default_false():
    cfg = RequestorConfig()
    assert cfg.force_localhost is False


def test_force_localhost_true():
    cfg = RequestorConfig(force_localhost=True)
    assert cfg.force_localhost is True


def test_discovery_url_production():
    cfg = RequestorConfig(environment="production")
    assert not cfg.discovery_url.startswith("DEVMODE-")


def test_db_path_not_overwritten(tmp_path):
    custom = tmp_path / "my.db"
    cfg = RequestorConfig(db_path=custom)
    assert cfg.db_path == custom


def test_get_provider_url_dev_mode():
    cfg = RequestorConfig(environment="development")
    url = cfg.get_provider_url("1.2.3.4")
    assert url == "http://1.2.3.4:7466"
