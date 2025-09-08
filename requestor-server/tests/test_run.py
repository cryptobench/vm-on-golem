import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from requestor.run import get_ssh_key_dir, secure_directory, check_requirements


def test_get_ssh_key_dir_env(monkeypatch, tmp_path):
    custom_dir = tmp_path / "ssh"
    monkeypatch.setenv("GOLEM_REQUESTOR_SSH_KEY_DIR", str(custom_dir))
    assert get_ssh_key_dir() == custom_dir


def test_secure_directory_creates_and_sets_permissions(tmp_path):
    target = tmp_path / "ssh"
    assert secure_directory(target)
    assert target.exists()
    assert (target.stat().st_mode & 0o777) == 0o700


def test_check_requirements_uses_secure_directory(monkeypatch, tmp_path):
    target = tmp_path / "ssh"
    monkeypatch.setenv("GOLEM_REQUESTOR_SSH_KEY_DIR", str(target))
    assert check_requirements()
    assert target.exists()
    assert (target.stat().st_mode & 0o777) == 0o700


def test_get_ssh_key_dir_default(monkeypatch, tmp_path):
    monkeypatch.delenv("GOLEM_REQUESTOR_SSH_KEY_DIR", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    expected = tmp_path / ".golem" / "requestor" / "ssh"
    assert get_ssh_key_dir() == expected


def test_secure_directory_failure(monkeypatch, tmp_path):
    target = tmp_path / "ssh"
    orig = Path.mkdir
    def bad_mkdir(self, parents=False, exist_ok=False):
        if self == target:
            raise OSError("fail")
        return orig(self, parents=parents, exist_ok=exist_ok)
    monkeypatch.setattr(Path, "mkdir", bad_mkdir)
    assert secure_directory(target) is False


def test_check_requirements_failure(monkeypatch):
    monkeypatch.setattr("requestor.run.secure_directory", lambda p: False)
    assert check_requirements() is False
