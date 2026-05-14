import subprocess
import sys
from pathlib import Path

import pytest

import provider.main as provider_main


@pytest.mark.parametrize(
    ("system", "env_name", "base_parts", "expected_parts"),
    [
        (
            "Darwin",
            "HOME",
            (),
            ("Library", "Application Support", "Golem Provider", "logs"),
        ),
        ("Windows", "APPDATA", ("Roaming",), ("Golem Provider", "logs")),
        ("Linux", "XDG_STATE_HOME", ("state",), ("golem-provider", "logs")),
    ],
)
def test_provider_daemon_log_dir_defaults_to_platform_app_data(
    monkeypatch, tmp_path, system, env_name, base_parts, expected_parts
):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.delenv("GOLEM_PROVIDER_LOG_DIR", raising=False)
    monkeypatch.setattr(provider_main._platform, "system", lambda: system)

    log_dir = Path(provider_main._provider_log_dir({}))
    base = tmp_path.joinpath(*base_parts)

    assert log_dir == base.joinpath(*expected_parts)
    assert log_dir.exists()


def test_provider_daemon_log_dir_respects_env_override(monkeypatch, tmp_path):
    custom = tmp_path / "custom-logs"
    monkeypatch.setenv("GOLEM_PROVIDER_LOG_DIR", str(custom))

    log_dir = Path(provider_main._provider_log_dir())

    assert log_dir == custom
    assert log_dir.exists()


def test_spawn_detached_redirects_stdio_to_rotating_log_file(monkeypatch, tmp_path):
    captured = {}

    class FakeProcess:
        pid = 12345

    def fake_popen(argv, **kwargs):
        captured["argv"] = argv
        captured.update(kwargs)
        return FakeProcess()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    monkeypatch.setattr(provider_main._platform, "system", lambda: "Darwin")

    pid = provider_main._spawn_detached(
        ["golem-provider", "start"],
        {
            "GOLEM_PROVIDER_LOG_DIR": str(tmp_path),
            "GOLEM_PROVIDER_LOG_MAX_BYTES": "256",
            "GOLEM_PROVIDER_LOG_BACKUPS": "2",
        },
    )

    assert pid == 12345
    assert captured["stdin"] is subprocess.DEVNULL
    assert captured["stderr"] is subprocess.STDOUT
    assert captured["stdout"] is not subprocess.DEVNULL
    assert Path(captured["stdout"].name) == tmp_path / "provider-daemon-stdio.log"
    assert captured["env"]["GOLEM_PROVIDER_LOG_DIR"] == str(tmp_path)


def test_spawn_detached_resets_pyinstaller_environment(monkeypatch, tmp_path):
    captured = {}

    class FakeProcess:
        pid = 12345

    def fake_popen(argv, **kwargs):
        captured.update(kwargs)
        return FakeProcess()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    monkeypatch.setattr(provider_main._platform, "system", lambda: "Darwin")
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    provider_main._spawn_detached(
        ["golem-provider", "start"],
        {"GOLEM_PROVIDER_LOG_DIR": str(tmp_path)},
    )

    assert captured["env"]["PYINSTALLER_RESET_ENVIRONMENT"] == "1"
