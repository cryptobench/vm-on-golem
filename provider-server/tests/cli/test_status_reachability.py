import json
import socket

import pytest
from typer.testing import CliRunner

import provider.main as provider_main
from provider.config import settings
from provider.main import cli
from provider.network_setup.domain import (
    PortCheck,
    SetupStage,
    SetupStageName,
    SetupStageState,
    StartupSetupStatus,
)
from provider.network_setup.status_store import write_startup_setup_status
from provider.vm.multipass_requirements import MultipassRequirementResult


@pytest.fixture
def status_cli_env(tmp_path, monkeypatch):
    api_socket = _listen_on_free_port()
    api_port = api_socket.getsockname()[1]
    port_start = _free_port()
    port_end = port_start + 3

    monkeypatch.setattr(settings, "PROXY_STATE_DIR", str(tmp_path), raising=False)
    monkeypatch.setattr(settings, "PORT_RANGE_START", port_start, raising=False)
    monkeypatch.setattr(settings, "PORT_RANGE_END", port_end, raising=False)
    monkeypatch.setattr(settings, "PORT", api_port, raising=False)
    monkeypatch.setattr(settings, "HOST", "0.0.0.0", raising=False)
    monkeypatch.setattr(settings, "PUBLIC_HTTPS_PORT", 4443, raising=False)
    monkeypatch.setattr(
        settings, "PORT_CHECK_TLS_URL", "https://checks.example", raising=False
    )
    monkeypatch.setattr(settings, "ENVIRONMENT", "production", raising=False)
    monkeypatch.setattr(settings, "NETWORK", "mainnet", raising=False)

    monkeypatch.setattr(provider_main, "_get_installed_version", lambda _pkg: "0.1.35")
    monkeypatch.setattr(
        provider_main, "_get_latest_version_from_pypi", lambda _pkg: None
    )
    monkeypatch.setattr(provider_main, "_multipass_requirement_result", _multipass_ok)

    async def check_public_https(_settings, endpoint_url):
        return {
            "status": "reachable",
            "verified_by": str(_settings.PORT_CHECK_TLS_URL),
            "error": None,
            "host": "203.0.113.10",
            "port": int(_settings.PUBLIC_HTTPS_PORT),
            "endpoint_url": endpoint_url,
        }

    monkeypatch.setattr(provider_main, "_check_public_https_status", check_public_https)

    try:
        yield {
            "tmp_path": tmp_path,
            "port_start": port_start,
            "port_end": port_end,
            "api_port": api_port,
        }
    finally:
        api_socket.close()


def test_status_uses_startup_verified_vm_range_for_free_capacity(status_cli_env):
    _write_startup_status(status_cli_env)

    result = CliRunner().invoke(cli, ["status", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ports"]["ssh"]["status"] == "ok"
    assert payload["ports"]["ssh"]["source"] == "startup"
    assert payload["ports"]["ssh"]["usable_free"] == 3
    assert payload["ports"]["ssh"]["in_use"] == 0
    assert "No externally reachable SSH ports" not in payload["overall"]["issues"]


def test_status_without_startup_status_is_unknown_not_blocked(status_cli_env):
    result = CliRunner().invoke(cli, ["status", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ports"]["ssh"]["status"] == "unknown"
    assert payload["ports"]["ssh"]["usable_free"] == 0
    assert "No externally reachable SSH ports" not in payload["overall"]["issues"]


def test_status_counts_active_proxy_ports_and_local_listening(status_cli_env):
    active_port = status_cli_env["port_start"]
    proxy_socket = _listen_on_port(active_port)
    _write_startup_status(status_cli_env)
    (status_cli_env["tmp_path"] / "proxy_state.json").write_text(
        json.dumps(
            {
                "version": 1,
                "proxies": {"vm-a": {"port": active_port, "target": "192.168.64.2"}},
            }
        )
    )

    try:
        result = CliRunner().invoke(cli, ["status", "--json"])
    finally:
        proxy_socket.close()

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ports"]["ssh"]["in_use"] == 1
    assert payload["ports"]["ssh"]["usable_free"] == 2
    active_detail = next(
        port for port in payload["ports"]["ssh"]["ports"] if port["port"] == active_port
    )
    assert active_detail["in_use"] is True
    assert active_detail["listening"] is True


def test_status_tty_does_not_report_no_free_ports(status_cli_env):
    _write_startup_status(status_cli_env)

    result = CliRunner().invoke(cli, ["status"])

    assert result.exit_code == 0
    assert "Provider Endpoint" in result.stdout
    assert "No free SSH ports available" not in result.stdout


def test_status_checks_public_https_not_raw_api_port(status_cli_env, monkeypatch):
    seen = {}

    async def check_public_https(_settings, endpoint_url):
        seen["api_port"] = int(_settings.PORT)
        seen["https_port"] = int(_settings.PUBLIC_HTTPS_PORT)
        seen["endpoint_url"] = endpoint_url
        return {
            "status": "reachable",
            "verified_by": "https://checks.example",
            "error": None,
            "host": "203.0.113.10",
            "port": int(_settings.PUBLIC_HTTPS_PORT),
            "endpoint_url": endpoint_url,
        }

    monkeypatch.setattr(provider_main, "_check_public_https_status", check_public_https)
    _write_startup_status(status_cli_env)

    result = CliRunner().invoke(cli, ["status", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert seen["api_port"] == status_cli_env["api_port"]
    assert seen["https_port"] == 4443
    assert payload["ports"]["provider"]["status"] == "reachable"
    assert payload["ports"]["provider"]["local_api"]["port"] == seen["api_port"]
    assert payload["ports"]["provider"]["public_https"]["port"] == 4443


def _write_startup_status(env):
    start = env["port_start"]
    end = env["port_end"]
    status = StartupSetupStatus(
        endpoint_url="https://203.0.113.10:4443",
        vm_port_range_start=start,
        vm_port_range_end=end,
        stages=[
            SetupStage(
                name=SetupStageName.VM_PORT_RANGE,
                label=f"VM ports {start}-{end} reachable",
                state=SetupStageState.SUCCESS,
                detail=f"{start}-{end} reachable",
                port_checks=[
                    PortCheck(port=port, state="open") for port in range(start, end)
                ],
            )
        ],
    )
    write_startup_setup_status(settings, status)


def _multipass_ok():
    return MultipassRequirementResult(
        installed=True,
        path="/usr/local/bin/multipass",
        version="1.16.1+mac",
        source="explicit",
        compatible=True,
        daemon_running=True,
        driver="qemu",
        action_required="",
    )


def _listen_on_free_port():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    sock.listen()
    return sock


def _listen_on_port(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", port))
    sock.listen()
    return sock


def _free_port():
    sock = _listen_on_free_port()
    port = sock.getsockname()[1]
    sock.close()
    return port
