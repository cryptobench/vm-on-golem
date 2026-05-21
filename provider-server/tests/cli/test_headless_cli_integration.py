import socket
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from typer.testing import CliRunner

from provider.config import settings
from provider.main import app, cli


ADMIN_TOKEN = "integration-admin"


@pytest.fixture(scope="module")
def provider_api(tmp_path_factory):
    vm_data_dir = tmp_path_factory.mktemp("provider-cli-api")
    old_config = dict(app.container.config())
    cfg = dict(old_config)
    cfg.update(
        {
            "PROVIDER_ADMIN_TOKEN": ADMIN_TOKEN,
            "VM_DATA_DIR": str(vm_data_dir),
            "STREAM_PAYMENT_ADDRESS": "0x1111111111111111111111111111111111111111",
            "PAYMENTS_RPC_URL": "http://127.0.0.1:9",
            "PROVIDER_ID": "0x2222222222222222222222222222222222222222",
            "COINGECKO_API_URL": "http://127.0.0.1:9",
        }
    )
    env_path = Path(__file__).parents[2] / ".env"
    original_env = env_path.read_text(encoding="utf-8") if env_path.exists() else None
    app.container.config.override(cfg)
    _reset_local_state()
    app.container.monitoring_repo().init_schema()

    port = _free_port()
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        lifespan="off",
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    _wait_for_port(port)
    try:
        yield f"http://127.0.0.1:{port}/api/v1"
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        app.container.config.override(old_config)
        _reset_local_state()
        if original_env is None:
            env_path.unlink(missing_ok=True)
        else:
            env_path.write_text(original_env, encoding="utf-8")


def test_headless_cli_commands_use_real_provider_api(
    provider_api, tmp_path, monkeypatch
):
    runner = CliRunner()
    monkeypatch.setenv("GOLEM_PROVIDER_LOG_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "COINGECKO_API_URL", "http://127.0.0.1:9")

    successful_commands = [
        ["info", "--api", provider_api, "--token", ADMIN_TOKEN, "--json"],
        ["summary", "--api", provider_api, "--token", ADMIN_TOKEN, "--json"],
        ["watch", "--api", provider_api, "--token", ADMIN_TOKEN, "--count", "1"],
        ["metrics", "--api", provider_api, "--token", ADMIN_TOKEN],
        ["vm", "list", "--api", provider_api, "--token", ADMIN_TOKEN, "--json"],
        ["stream", "list", "--api", provider_api, "--token", ADMIN_TOKEN, "--json"],
        ["stream", "earnings", "--api", provider_api, "--token", ADMIN_TOKEN, "--json"],
        ["stream", "withdraw", "--all"],
        [
            "monitor",
            "--api",
            provider_api,
            "--token",
            ADMIN_TOKEN,
            "--watch",
            "--count",
            "1",
            "--json",
        ],
        [
            "monitor",
            "history",
            "--api",
            provider_api,
            "--token",
            ADMIN_TOKEN,
            "--json",
        ],
        ["monitor", "vm", "missing-vm", "--api", provider_api, "--token", ADMIN_TOKEN],
        ["alert", "list", "--api", provider_api, "--token", ADMIN_TOKEN, "--json"],
        ["alert", "rules", "--api", provider_api, "--token", ADMIN_TOKEN, "--json"],
        [
            "alert",
            "add",
            "--api",
            provider_api,
            "--token",
            ADMIN_TOKEN,
            "--name",
            "Integration CPU",
            "--metric",
            "cpu_percent",
            "--scope",
            "host",
            "--source",
            "infrastructure",
            "--op",
            ">",
            "--threshold",
            "95",
            "--for",
            "60",
            "--severity",
            "warning",
            "--json",
        ],
        ["webhook", "list", "--api", provider_api, "--token", ADMIN_TOKEN, "--json"],
        [
            "webhook",
            "add",
            "--api",
            provider_api,
            "--token",
            ADMIN_TOKEN,
            "--name",
            "Integration webhook",
            "--url",
            "http://127.0.0.1:9/webhook",
            "--service",
            "generic_json",
            "--event",
            "alert.fired",
            "--json",
        ],
        [
            "webhook",
            "edit",
            "1",
            "--api",
            provider_api,
            "--token",
            ADMIN_TOKEN,
            "--name",
            "Integration webhook updated",
            "--event",
            "vm.ready",
            "--json",
        ],
        [
            "webhook",
            "show",
            "1",
            "--api",
            provider_api,
            "--token",
            ADMIN_TOKEN,
            "--json",
        ],
        ["webhook", "disable", "1", "--api", provider_api, "--token", ADMIN_TOKEN],
        ["webhook", "enable", "1", "--api", provider_api, "--token", ADMIN_TOKEN],
        [
            "webhook",
            "test",
            "1",
            "--api",
            provider_api,
            "--token",
            ADMIN_TOKEN,
            "--event",
            "vm.ready",
            "--json",
        ],
        [
            "webhook",
            "deliveries",
            "1",
            "--api",
            provider_api,
            "--token",
            ADMIN_TOKEN,
            "--json",
        ],
        [
            "webhook",
            "delete",
            "1",
            "--api",
            provider_api,
            "--token",
            ADMIN_TOKEN,
            "--yes",
        ],
        ["settings", "--api", provider_api, "--token", ADMIN_TOKEN, "--json"],
        [
            "settings",
            "resources",
            "--api",
            provider_api,
            "--token",
            ADMIN_TOKEN,
            "--json",
        ],
        [
            "settings",
            "resources",
            "set",
            "--api",
            provider_api,
            "--token",
            ADMIN_TOKEN,
            "--cpu",
            "1",
            "--memory",
            "1",
            "--storage",
            "1",
            "--json",
        ],
        [
            "settings",
            "pricing",
            "--api",
            provider_api,
            "--token",
            ADMIN_TOKEN,
            "--json",
        ],
        [
            "settings",
            "pricing",
            "set",
            "--api",
            provider_api,
            "--token",
            ADMIN_TOKEN,
            "--cpu",
            "1",
            "--memory",
            "1",
            "--storage",
            "1",
            "--json",
        ],
        [
            "settings",
            "pricing",
            "calc",
            "--api",
            provider_api,
            "--token",
            ADMIN_TOKEN,
            "--cpu",
            "1",
            "--memory",
            "1",
            "--storage",
            "1",
            "--json",
        ],
    ]

    for command in successful_commands:
        result = runner.invoke(cli, command)
        assert result.exit_code == 0, (command, result.stdout, result.exception)


def test_headless_cli_failure_commands_use_real_provider_api(provider_api):
    runner = CliRunner()
    failing_commands = [
        ["vm", "show", "missing-vm", "--api", provider_api, "--token", ADMIN_TOKEN],
        ["vm", "access", "missing-vm", "--api", provider_api, "--token", ADMIN_TOKEN],
        ["vm", "ssh", "missing-vm", "--api", provider_api, "--token", ADMIN_TOKEN],
        [
            "vm",
            "terminate",
            "missing-vm",
            "--api",
            provider_api,
            "--token",
            ADMIN_TOKEN,
            "--yes",
        ],
        ["stream", "show", "missing-vm", "--api", provider_api, "--token", ADMIN_TOKEN],
    ]

    for command in failing_commands:
        result = runner.invoke(cli, command)
        assert result.exit_code != 0, (command, result.stdout)
        assert "Error:" in result.stderr or "Error:" in result.stdout


def test_doctor_command_without_starting_provider(tmp_path, monkeypatch):
    runner = CliRunner()
    monkeypatch.setenv("GOLEM_PROVIDER_LOG_DIR", str(tmp_path))

    doctor = runner.invoke(cli, ["doctor", "--json"])
    assert doctor.exit_code in (0, 1)
    assert "requirements" in doctor.stdout


def _reset_local_state() -> None:
    for provider in (
        app.container.monitoring_repo,
        app.container.webhook_repo,
        app.container.monitoring_service,
        app.container.webhook_service,
        app.container.provider_settings_service,
        app.container.summary_service,
        app.container.provider_auth_service,
        app.container.stream_map,
        app.container.vm_service,
        app.container.vm_application_service,
    ):
        try:
            provider.reset()
        except Exception:
            pass


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_port(port: int) -> None:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.2)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.05)
    raise RuntimeError(f"test provider API did not start on port {port}")
