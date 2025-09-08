from pathlib import Path
import subprocess

import pytest

import sys
sys.path.append(str(Path(__file__).resolve().parents[1]))

from requestor.services.ssh_service import SSHService
from requestor.errors import SSHError


def test_format_ssh_command(tmp_path):
    svc = SSHService(tmp_path)
    cmd = svc.format_ssh_command("host", 22, tmp_path / "key")
    assert "ssh -i" in cmd and "host" in cmd


def test_parse_stats():
    svc = SSHService(Path("/tmp"))
    sample = (
        "%Cpu(s): 70.0 us, 30.0 id\n"
        "MiB Mem : 2000 total, 1000 used, 1000 free\n"
        "/dev/sda1 100G 50G 50G 50% /"
    )
    stats = svc._parse_stats(sample)
    assert stats["cpu"]["usage"] == "70.0%"
    assert stats["memory"]["total"].endswith("MiB")
    assert stats["disk"]["used"] == "50G"


def test_format_ssh_command_colorize(tmp_path, monkeypatch):
    svc = SSHService(tmp_path)
    import click
    monkeypatch.setattr(click, "style", lambda x, **k: f"c:{x}")
    cmd = svc.format_ssh_command("h", 22, tmp_path / "k", colorize=True)
    assert cmd.startswith("c:")


def test_get_key_pair_sync_error(tmp_path, monkeypatch):
    svc = SSHService(tmp_path)
    def boom():
        raise RuntimeError("x")
    monkeypatch.setattr(svc.ssh_manager, "get_key_pair_sync", boom)
    with pytest.raises(SSHError):
        svc.get_key_pair_sync()


def test_connect_to_vm_calls_subprocess(tmp_path, monkeypatch):
    svc = SSHService(tmp_path)
    called = {}
    def fake_run(cmd, check):
        called["cmd"] = cmd
    monkeypatch.setattr(subprocess, "run", fake_run)
    svc.connect_to_vm("host", 22, tmp_path / "k")
    assert called["cmd"][0] == "ssh"


def test_connect_to_vm_error(tmp_path, monkeypatch):
    svc = SSHService(tmp_path)
    def fake_run(cmd, check):
        raise RuntimeError("bad")
    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(SSHError):
        svc.connect_to_vm("host", 22, tmp_path / "k")


def test_get_vm_stats_error(tmp_path, monkeypatch):
    svc = SSHService(tmp_path)
    def fake_run(*a, **k):
        raise subprocess.CalledProcessError(1, "cmd", "err")
    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(SSHError):
        svc.get_vm_stats("h", 22, tmp_path / "k")
