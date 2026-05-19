import importlib.util
import sys
from pathlib import Path


def load_local_stack_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "local_stack.py"
    spec = importlib.util.spec_from_file_location("vm_on_golem_local_stack", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def deployment():
    return {
        "rpc_url": "http://127.0.0.1:8545",
        "stream_payment_address": "0x0000000000000000000000000000000000000000",
        "glm_token_address": "0x0000000000000000000000000000000000000000",
    }


def test_local_stack_default_log_config_uses_repo_local_logs(monkeypatch):
    local_stack = load_local_stack_module()
    monkeypatch.delenv("LOCAL_STACK_LOG_DIR", raising=False)
    monkeypatch.delenv("LOCAL_STACK_LOG_MAX_BYTES", raising=False)
    monkeypatch.delenv("LOCAL_STACK_LOG_BACKUPS", raising=False)

    config = local_stack.default_log_config()

    assert config.log_dir == local_stack.ROOT / ".local" / "logs"
    assert config.max_bytes == 10 * 1024 * 1024
    assert config.backups == 5


def test_local_stack_parses_custom_log_args(tmp_path):
    local_stack = load_local_stack_module()

    args = local_stack.parse_args(
        [
            "--log-dir",
            str(tmp_path),
            "--log-max-bytes",
            "128",
            "--log-backups",
            "2",
        ]
    )

    assert args.log_dir == str(tmp_path)
    assert args.log_max_bytes == 128
    assert args.log_backups == 2


def test_local_stack_writes_aggregate_setup_and_service_logs(tmp_path):
    local_stack = load_local_stack_module()
    sink = local_stack.configure_stack_logging(
        local_stack.LogConfig(log_dir=tmp_path, max_bytes=1024, backups=1)
    )

    local_stack.log("supervisor line")
    local_stack.log_setup("setup line")
    local_stack.log_service("provider", "provider line", echo=False)
    sink.close()

    assert "supervisor line" in (tmp_path / "local-stack.log").read_text()
    assert "setup line" in (tmp_path / "local-stack.log").read_text()
    assert "provider line" in (tmp_path / "local-stack.log").read_text()
    assert "setup line" in (tmp_path / "setup.log").read_text()
    assert "provider line" in (tmp_path / "provider.log").read_text()


def test_local_stack_can_echo_tailed_logs_without_rewriting_source_log(tmp_path):
    local_stack = load_local_stack_module()
    sink = local_stack.configure_stack_logging(
        local_stack.LogConfig(log_dir=tmp_path, max_bytes=1024, backups=1)
    )

    local_stack.log_service(
        "provider",
        "provider file tail line",
        echo=False,
        write_service_log=False,
    )
    sink.close()

    assert "provider file tail line" in (tmp_path / "local-stack.log").read_text()
    assert not (tmp_path / "provider.log").exists()


def test_local_stack_logs_setup_command_output(tmp_path):
    local_stack = load_local_stack_module()
    sink = local_stack.configure_stack_logging(
        local_stack.LogConfig(log_dir=tmp_path, max_bytes=1024, backups=1)
    )

    local_stack.run_checked(
        [sys.executable, "-c", "print('setup command output')"],
        cwd=local_stack.ROOT,
    )
    sink.close()

    assert "setup command output" in (tmp_path / "setup.log").read_text()
    assert "setup command output" in (tmp_path / "local-stack.log").read_text()


def test_local_stack_build_services_passes_log_env_to_every_service(tmp_path):
    local_stack = load_local_stack_module()
    sink = local_stack.configure_stack_logging(
        local_stack.LogConfig(log_dir=tmp_path, max_bytes=2048, backups=3)
    )

    services = [
        *local_stack.build_services(
            deployment=deployment(),
            start_provider_desktop=False,
        ),
        *local_stack.build_services(
            deployment=deployment(),
            start_provider_desktop=True,
        ),
    ]
    sink.close()

    service_names = {service.name for service in services}
    assert {
        "central-discovery",
        "provider",
        "requestor-web",
        "provider-desktop",
    }.issubset(service_names)

    for service in services:
        assert service.env["GOLEM_LOCAL_STACK_LOG_DIR"] == str(tmp_path)
        assert service.env["GOLEM_LOCAL_STACK_LOG_MAX_BYTES"] == "2048"
        assert service.env["GOLEM_LOCAL_STACK_LOG_BACKUPS"] == "3"
        assert service.env["PYTHONUNBUFFERED"] == "1"

    providers = [service for service in services if service.name == "provider"]
    provider = providers[0]
    provider_desktop = next(
        service for service in services if service.name == "provider-desktop"
    )
    central = next(
        service for service in services if service.name == "central-discovery"
    )
    assert central.command == ["go", "run", "./cmd/golem-central-discovery"]
    assert central.cwd == local_stack.ROOT / "central-discovery-server"
    requestor_web = next(
        service for service in services if service.name == "requestor-web"
    )

    assert provider.env["GOLEM_PROVIDER_LOG_DIR"] == str(tmp_path)
    assert any(service.write_service_log is False for service in providers)
    assert provider_desktop.env["GOLEM_PROVIDER_LOG_DIR"] == str(tmp_path)
    assert central.env["GOLEM_CENTRAL_DISCOVERY_LOG_DIR"] == str(tmp_path)
    assert "GOLEM_PROVIDER_PORT_CHECK_TLS_URL" not in provider.env
    assert requestor_web.command == [
        "npm",
        "--prefix",
        "requestor-web",
        "run",
        "dev",
        "--",
        "--hostname",
        "127.0.0.1",
        "--port",
        "3000",
    ]
    assert requestor_web.env["NEXT_PUBLIC_GOLEM_ENVIRONMENT"] == "development"
    assert (
        requestor_web.env["NEXT_PUBLIC_DISCOVERY_WS_URL"]
        == "ws://127.0.0.1:9001/api/v1/discovery/requestors"
    )
    assert (
        requestor_web.env["NEXT_PUBLIC_STREAM_PAYMENT_ADDRESS"]
        == deployment()["stream_payment_address"]
    )
    assert (
        requestor_web.env["NEXT_PUBLIC_GLM_TOKEN_ADDRESS"]
        == deployment()["glm_token_address"]
    )
    assert requestor_web.env["NEXT_PUBLIC_EVM_CHAIN_ID"] == "0x88bb0"
    assert requestor_web.env["NEXT_PUBLIC_EVM_CHAIN_NAME"] == "Ethereum Hoodi"
    assert requestor_web.env["NEXT_PUBLIC_EVM_RPC_URL"] == deployment()["rpc_url"]
    assert (
        requestor_web.env["NEXT_PUBLIC_EVM_WS_URL"]
        == "wss://ethereum-hoodi-rpc.publicnode.com"
    )
    assert (
        requestor_web.env["NEXT_PUBLIC_EVM_EXPLORER_URL"]
        == "https://hoodi.etherscan.io"
    )
    assert requestor_web.env["WATCHPACK_POLLING"] == "true"
    assert requestor_web.env["CHOKIDAR_USEPOLLING"] == "true"


def test_local_stack_binds_provider_for_guest_metrics():
    local_stack = load_local_stack_module()
    services = local_stack.build_services(
        deployment=deployment(),
        start_provider_desktop=False,
    )

    provider = next(service for service in services if service.name == "provider")

    assert provider.env["GOLEM_PROVIDER_HOST"] == "0.0.0.0"
    assert provider.env["GOLEM_PROVIDER_PUBLIC_IP"] == "auto"


def test_local_stack_syncs_existing_provider_tauri_sidecars(monkeypatch, tmp_path):
    local_stack = load_local_stack_module()
    monkeypatch.setattr(local_stack, "ROOT", tmp_path)
    monkeypatch.setattr(local_stack.os, "name", "posix")

    sidecar = (
        tmp_path
        / "apps"
        / "provider-desktop"
        / "src-tauri"
        / "binaries"
        / "golem-provider-aarch64-apple-darwin"
    )
    debug_sidecar = (
        tmp_path
        / "apps"
        / "provider-desktop"
        / "src-tauri"
        / "target"
        / "debug"
        / "golem-provider"
    )
    release_sidecar = (
        tmp_path
        / "apps"
        / "provider-desktop"
        / "src-tauri"
        / "target"
        / "release"
        / "golem-provider"
    )
    sidecar.parent.mkdir(parents=True)
    debug_sidecar.parent.mkdir(parents=True)
    release_sidecar.parent.mkdir(parents=True)
    sidecar.write_text("fixed")
    debug_sidecar.write_text("old")
    release_sidecar.write_text("old")

    local_stack.sync_existing_provider_tauri_sidecars(sidecar)

    assert debug_sidecar.read_text() == "fixed"
    assert release_sidecar.read_text() == "fixed"
