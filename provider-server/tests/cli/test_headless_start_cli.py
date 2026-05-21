from typer.testing import CliRunner

import provider.main as provider_main
from provider.main import cli


def test_start_defaults_to_foreground_server(monkeypatch):
    calls = []

    monkeypatch.setattr(
        provider_main,
        "_provider_admin_env",
        lambda: {
            "GOLEM_PROVIDER_ADMIN_TOKEN": "admin",
            "GOLEM_PROVIDER_VM_DATA_DIR": "/tmp/vms",
        },
    )
    monkeypatch.setattr(
        provider_main,
        "_run_startup_preflight",
        lambda no_verify_port: calls.append(("preflight", no_verify_port)),
    )
    monkeypatch.setattr(
        provider_main,
        "run_server",
        lambda **kwargs: calls.append(("server", kwargs)),
    )

    result = CliRunner().invoke(cli, ["start", "--no-verify-port"])

    assert result.exit_code == 0
    assert "Provider startup checks passed." in result.stdout
    assert "Provider server is starting in the foreground." in result.stdout
    assert "Press Ctrl+C to stop." in result.stdout
    assert ("preflight", True) in calls
    assert calls[-1][0] == "server"
    assert calls[-1][1]["dev_mode"] is None
    assert calls[-1][1]["no_verify_port"] is True


def test_start_runs_preflight_then_server_with_port_verification(monkeypatch):
    calls = []

    monkeypatch.setattr(
        provider_main,
        "_provider_admin_env",
        lambda: {
            "GOLEM_PROVIDER_ADMIN_TOKEN": "admin",
            "GOLEM_PROVIDER_VM_DATA_DIR": "/tmp/vms",
        },
    )
    monkeypatch.setattr(
        provider_main,
        "_run_startup_preflight",
        lambda no_verify_port: calls.append(("preflight", no_verify_port)),
    )
    monkeypatch.setattr(
        provider_main,
        "run_server",
        lambda **kwargs: calls.append(("server", kwargs)),
    )

    result = CliRunner().invoke(cli, ["start", "--network", "development"])

    assert result.exit_code == 0
    assert "Provider startup checks passed." in result.stdout
    assert "Provider server is starting in the foreground." in result.stdout
    assert "Press Ctrl+C to stop." in result.stdout
    assert ("preflight", False) in calls
    assert calls[-1][0] == "server"
    assert calls[-1][1]["network"] == "development"
    assert calls[-1][1]["no_verify_port"] is False


def test_run_server_disables_reload_for_desktop_sidecar(monkeypatch):
    import uvicorn

    calls = []

    monkeypatch.setenv("GOLEM_ENVIRONMENT", "development")
    monkeypatch.setenv("GOLEM_PROVIDER_DISABLE_RELOAD", "1")
    monkeypatch.setattr(provider_main, "check_requirements", lambda: True)
    monkeypatch.setattr(uvicorn, "run", lambda *args, **kwargs: calls.append(kwargs))

    provider_main.run_server(dev_mode=None, no_verify_port=True)

    assert calls
    assert calls[-1]["reload"] is False


def test_run_server_keeps_reload_for_normal_development(monkeypatch):
    import uvicorn

    calls = []

    monkeypatch.setenv("GOLEM_ENVIRONMENT", "development")
    monkeypatch.delenv("GOLEM_PROVIDER_DISABLE_RELOAD", raising=False)
    monkeypatch.setattr(provider_main, "check_requirements", lambda: True)
    monkeypatch.setattr(uvicorn, "run", lambda *args, **kwargs: calls.append(kwargs))

    provider_main.run_server(dev_mode=None, no_verify_port=True)

    assert calls
    assert calls[-1]["reload"] is True


def test_provider_env_log_value_redacts_admin_token():
    assert (
        provider_main._provider_env_log_value(
            "GOLEM_PROVIDER_ADMIN_TOKEN", "admin-secret"
        )
        == "<redacted>"
    )
    assert (
        provider_main._provider_env_log_value(
            "GOLEM_PROVIDER_GLM_TOKEN_ADDRESS", "0x5555"
        )
        == "0x5555"
    )
