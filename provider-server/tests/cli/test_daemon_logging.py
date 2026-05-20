import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

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


@pytest.mark.asyncio
async def test_secure_setup_preflight_resolves_location_before_network_setup(
    monkeypatch,
):
    from provider.config import settings
    from provider.network.location_resolver import ProviderLocation

    calls = []

    async def resolve(location_settings):
        location = ProviderLocation(ip_address="127.0.0.1", country="DK")
        monkeypatch.setattr(location_settings, "PUBLIC_IP", location.ip_address)
        monkeypatch.setattr(location_settings, "PROVIDER_COUNTRY", location.country)
        calls.append("resolve")
        return location

    class FakeNetworkSetupService:
        def __init__(self, service_settings, status_callback=None):
            self.settings = service_settings
            self.status_callback = status_callback

        async def setup(self):
            calls.append(
                (
                    "setup",
                    self.settings.PUBLIC_IP,
                    self.settings.PROVIDER_COUNTRY,
                )
            )
            return SimpleNamespace(model_dump=lambda mode: {"complete": True})

        async def cleanup(self):
            calls.append("cleanup")

    monkeypatch.setattr(
        "provider.network.location_resolver.ensure_provider_location",
        resolve,
    )
    monkeypatch.setattr(
        "provider.network_setup.service.NetworkSetupService",
        FakeNetworkSetupService,
    )
    monkeypatch.setattr(settings, "PUBLIC_IP", None)
    monkeypatch.setattr(settings, "PROVIDER_COUNTRY", None)

    status = await provider_main._run_secure_setup_preflight()

    assert status == {"complete": True}
    assert calls == ["resolve", ("setup", "127.0.0.1", "DK"), "cleanup"]


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


def test_terminate_process_tree_stops_daemon_children(monkeypatch):
    class FakeProcess:
        def __init__(self, pid, children=None):
            self.pid = pid
            self._children = children or []
            self.terminated = False
            self.killed = False

        def children(self, recursive=True):
            assert recursive is True
            return self._children

        def terminate(self):
            self.terminated = True

        def kill(self):
            self.killed = True

    child = FakeProcess(200)
    parent = FakeProcess(100, [child])

    def fake_process(pid):
        assert pid == 100
        return parent

    def fake_wait_procs(processes, timeout):
        assert timeout == 5
        return list(processes), []

    monkeypatch.setattr(provider_main.psutil, "Process", fake_process)
    monkeypatch.setattr(provider_main.psutil, "wait_procs", fake_wait_procs)

    assert provider_main._terminate_process_tree(100, 5) is True
    assert parent.terminated is True
    assert child.terminated is True
    assert parent.killed is False
    assert child.killed is False
