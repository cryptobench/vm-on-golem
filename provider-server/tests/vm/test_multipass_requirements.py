import subprocess
from pathlib import Path
from typing import Sequence

import pytest

from provider.vm.multipass_requirements import (
    MultipassCompatibilityError,
    check_host_virtualization_compatibility,
    check_multipass_requirements,
)


def _fake_binary(tmp_path: Path, name: str = "multipass") -> str:
    binary = tmp_path / name
    binary.write_text("#!/bin/sh\nexit 0\n")
    binary.chmod(0o755)
    return str(binary)


def _runner(responses: dict[tuple[str, ...], subprocess.CompletedProcess[str]]):
    def run(command: Sequence[str], timeout: int) -> subprocess.CompletedProcess[str]:
        key = tuple(command[1:])
        return responses.get(
            key,
            subprocess.CompletedProcess(command, 0, stdout="", stderr=""),
        )

    return run


def test_reports_missing_multipass(monkeypatch):
    monkeypatch.setattr(
        "provider.vm.multipass_requirements.detect_multipass_binary",
        lambda explicit_path=None: None,
    )

    result = check_multipass_requirements()

    assert result.installed is False
    assert result.compatible is False
    assert result.action_required == "install"
    assert result.error


def test_accepts_valid_multipass(tmp_path):
    multipass = _fake_binary(tmp_path)
    run = _runner(
        {
            ("version",): subprocess.CompletedProcess(
                [multipass, "version"], 0, stdout="multipass 1.16.2+linux\n"
            ),
            ("get", "local.driver"): subprocess.CompletedProcess(
                [multipass, "get", "local.driver"], 0, stdout="qemu\n"
            ),
            ("list", "--format", "json"): subprocess.CompletedProcess(
                [multipass, "list", "--format", "json"], 0, stdout='{"list":[]}'
            ),
        }
    )

    result = check_multipass_requirements(explicit_path=multipass, run_command=run)

    assert result.installed is True
    assert result.compatible is True
    assert result.daemon_running is True
    assert result.version == "1.16.2+linux"
    assert result.action_required == "none"


def test_rejects_too_old_multipass(tmp_path):
    multipass = _fake_binary(tmp_path)
    run = _runner(
        {
            ("version",): subprocess.CompletedProcess(
                [multipass, "version"], 0, stdout="multipass 1.12.0+linux\n"
            ),
            ("list", "--format", "json"): subprocess.CompletedProcess(
                [multipass, "list", "--format", "json"], 0, stdout='{"list":[]}'
            ),
        }
    )

    result = check_multipass_requirements(explicit_path=multipass, run_command=run)

    assert result.compatible is False
    assert result.action_required == "upgrade"
    assert "below the minimum" in (result.error or "")


def test_accepts_newer_multipass_by_default(tmp_path):
    multipass = _fake_binary(tmp_path)
    run = _runner(
        {
            ("version",): subprocess.CompletedProcess(
                [multipass, "version"], 0, stdout="multipass 1.17.0+linux\n"
            ),
            ("list", "--format", "json"): subprocess.CompletedProcess(
                [multipass, "list", "--format", "json"], 0, stdout='{"list":[]}'
            ),
        }
    )

    result = check_multipass_requirements(explicit_path=multipass, run_command=run)

    assert result.compatible is True


def test_rejects_blocked_multipass_version(tmp_path):
    multipass = _fake_binary(tmp_path)
    run = _runner(
        {
            ("version",): subprocess.CompletedProcess(
                [multipass, "version"], 0, stdout="multipass 1.16.2+linux\n"
            ),
            ("list", "--format", "json"): subprocess.CompletedProcess(
                [multipass, "list", "--format", "json"], 0, stdout='{"list":[]}'
            ),
        }
    )

    result = check_multipass_requirements(
        explicit_path=multipass,
        run_command=run,
        blocked_versions={"1.16.2+linux"},
    )

    assert result.compatible is False
    assert result.action_required == "upgrade"
    assert "blocked" in (result.error or "")


def test_reports_daemon_not_running(tmp_path):
    multipass = _fake_binary(tmp_path)
    run = _runner(
        {
            ("version",): subprocess.CompletedProcess(
                [multipass, "version"], 0, stdout="multipass 1.16.2+linux\n"
            ),
            ("list", "--format", "json"): subprocess.CompletedProcess(
                [multipass, "list", "--format", "json"], 1, stderr="daemon down"
            ),
        }
    )

    result = check_multipass_requirements(explicit_path=multipass, run_command=run)

    assert result.compatible is False
    assert result.action_required == "repair"
    assert result.daemon_running is False
    assert "daemon" in (result.error or "")


def test_rejects_known_broken_apple_silicon_qemu(monkeypatch, tmp_path):
    qemu = tmp_path / "qemu-system-aarch64"
    qemu.write_text("#!/bin/sh\nexit 0\n")
    qemu.chmod(0o755)
    multipass = _fake_binary(tmp_path)

    run = _runner(
        {
            ("get", "local.driver"): subprocess.CompletedProcess(
                [multipass, "get", "local.driver"], 0, stdout="qemu\n"
            ),
            ("version",): subprocess.CompletedProcess(
                [multipass, "version"], 0, stdout="multipass 1.16.2+mac\n"
            ),
            ("--version",): subprocess.CompletedProcess(
                [str(qemu), "--version"],
                0,
                stdout="QEMU emulator version 8.2.1\n",
            ),
        }
    )

    monkeypatch.setattr(
        "provider.vm.multipass_requirements.platform.system", lambda: "Darwin"
    )
    monkeypatch.setattr(
        "provider.vm.multipass_requirements.platform.machine", lambda: "arm64"
    )
    monkeypatch.setattr(
        "provider.vm.multipass_requirements.platform.release", lambda: "25.2.0"
    )

    with pytest.raises(MultipassCompatibilityError, match="host-arm-cpu.sme"):
        check_host_virtualization_compatibility(multipass, run_command=run)
