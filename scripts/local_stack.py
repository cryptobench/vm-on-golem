#!/usr/bin/env python3
"""Run the local VM on Golem development stack."""

from __future__ import annotations

import argparse
import json
import logging
import os
import platform
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import textwrap
import urllib.error
import urllib.request
import webbrowser
from dataclasses import dataclass, field
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
LOCAL_DIR = ROOT / ".local"

CENTRAL_HOST = "127.0.0.1"
CENTRAL_PORT = 9001
PROVIDER_BIND_HOST = "0.0.0.0"
PROVIDER_HOST = "127.0.0.1"
PROVIDER_PORT = 7466
PORT_CHECKER_HOST = "127.0.0.1"
PORT_CHECKER_PORT = 9000
REQUESTOR_HOST = "127.0.0.1"
REQUESTOR_PORT = 8000
WEB_HOST = "127.0.0.1"
WEB_PORT = 3000
PROVIDER_DESKTOP_HOST = "127.0.0.1"
PROVIDER_DESKTOP_PORT = 1420
WEB_WATCH_ENV_DEFAULTS = {
    "WATCHPACK_POLLING": "true",
    "WATCHPACK_POLLING_INTERVAL": "1000",
    "CHOKIDAR_USEPOLLING": "true",
    "CHOKIDAR_INTERVAL": "1000",
}

CENTRAL_URL = f"http://{CENTRAL_HOST}:{CENTRAL_PORT}"
CENTRAL_API_URL = f"{CENTRAL_URL}/api/v1"
PROVIDER_API_URL = f"http://{PROVIDER_HOST}:{PROVIDER_PORT}/api/v1"
PORT_CHECKER_URL = f"http://{PORT_CHECKER_HOST}:{PORT_CHECKER_PORT}"
REQUESTOR_API_URL = f"http://{REQUESTOR_HOST}:{REQUESTOR_PORT}/api/v1"
WEB_URL = f"http://{WEB_HOST}:{WEB_PORT}"
PROVIDER_DESKTOP_URL = f"http://{PROVIDER_DESKTOP_HOST}:{PROVIDER_DESKTOP_PORT}"
ARKIV_RPC_URL = "https://kaolin.hoodi.arkiv.network/rpc"
ARKIV_WS_URL = "wss://kaolin.hoodi.arkiv.network/rpc/ws"
L2_RPC_URL = "https://rpc.hoodi.ethpandaops.io"
L2_RPC_FALLBACK_URLS = [
    L2_RPC_URL,
]
L2_WS_URL = ""
L2_FAUCET_URL = ""
L2_EXPLORER_URL = "https://hoodi.etherscan.io"
L2_CHAIN_ID_DEC = "560048"
L2_CHAIN_ID_HEX = "0x88bb0"
PAYMENTS_NETWORK = "hoodi"
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
DEFAULT_LOG_MAX_BYTES = 10 * 1024 * 1024
DEFAULT_LOG_BACKUPS = 5
LOCAL_STACK_LOG_DIR_ENV = "LOCAL_STACK_LOG_DIR"
LOCAL_STACK_LOG_MAX_BYTES_ENV = "LOCAL_STACK_LOG_MAX_BYTES"
LOCAL_STACK_LOG_BACKUPS_ENV = "LOCAL_STACK_LOG_BACKUPS"


class LocalStackError(RuntimeError):
    """Raised when the local stack cannot start or run."""


@dataclass
class Service:
    name: str
    command: list[str]
    env: dict[str, str] = field(default_factory=dict)
    cwd: Path = ROOT
    ready: Callable[[], bool] | None = None
    fatal: bool = True
    write_service_log: bool = True
    process: subprocess.Popen[str] | None = None


@dataclass(frozen=True)
class LogConfig:
    log_dir: Path
    max_bytes: int = DEFAULT_LOG_MAX_BYTES
    backups: int = DEFAULT_LOG_BACKUPS

    def __post_init__(self) -> None:
        if self.max_bytes < 0:
            raise LocalStackError("Log max bytes must be non-negative")
        if self.backups < 0:
            raise LocalStackError("Log backups must be non-negative")


class StackLogSink:
    """Write stack output to aggregate and per-source rotating logs."""

    def __init__(self, config: LogConfig) -> None:
        self.config = config
        self.config.log_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._handlers: dict[str, RotatingFileHandler] = {}
        self._formatter = logging.Formatter("%(message)s")

    def path_for(self, name: str) -> Path:
        return self.config.log_dir / f"{name}.log"

    def write(self, name: str, message: str) -> None:
        text = message.rstrip("\n")
        if not text:
            return
        with self._lock:
            self._emit("local-stack", text)
            if name != "local-stack":
                self._emit(name, text)

    def close(self) -> None:
        with self._lock:
            for handler in self._handlers.values():
                handler.close()
            self._handlers.clear()

    def _emit(self, name: str, message: str) -> None:
        record = logging.LogRecord(
            name=f"local-stack.{name}",
            level=logging.INFO,
            pathname=__file__,
            lineno=0,
            msg=message,
            args=(),
            exc_info=None,
        )
        self._handler(name).handle(record)

    def _handler(self, name: str) -> RotatingFileHandler:
        handler = self._handlers.get(name)
        if handler is not None:
            return handler
        handler = RotatingFileHandler(
            self.path_for(name),
            maxBytes=self.config.max_bytes,
            backupCount=self.config.backups,
            encoding="utf-8",
        )
        handler.setFormatter(self._formatter)
        self._handlers[name] = handler
        return handler


_stack_log_config: LogConfig | None = None
_stack_logs: StackLogSink | None = None


def default_log_config() -> LogConfig:
    return LogConfig(
        log_dir=Path(os.environ.get(LOCAL_STACK_LOG_DIR_ENV, LOCAL_DIR / "logs")),
        max_bytes=env_int(LOCAL_STACK_LOG_MAX_BYTES_ENV, DEFAULT_LOG_MAX_BYTES),
        backups=env_int(LOCAL_STACK_LOG_BACKUPS_ENV, DEFAULT_LOG_BACKUPS),
    )


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise LocalStackError(f"{name} must be an integer") from exc
    if value < 0:
        raise LocalStackError(f"{name} must be non-negative")
    return value


def configure_stack_logging(config: LogConfig) -> StackLogSink:
    global _stack_log_config, _stack_logs
    if _stack_logs is not None:
        _stack_logs.close()
    _stack_log_config = config
    _stack_logs = StackLogSink(config)
    return _stack_logs


def current_log_config() -> LogConfig:
    return _stack_log_config or default_log_config()


def log(message: str) -> None:
    print(message, flush=True)
    if _stack_logs is not None:
        _stack_logs.write("local-stack", message)


def log_setup(message: str) -> None:
    print(message, flush=True)
    if _stack_logs is not None:
        _stack_logs.write("setup", message)


def log_service(
    service_name: str,
    message: str,
    *,
    echo: bool = True,
    write_service_log: bool = True,
) -> None:
    if echo:
        print(message, flush=True)
    if _stack_logs is not None:
        log_name = service_name if write_service_log else "local-stack"
        _stack_logs.write(log_name, message)


def stack_log_env() -> dict[str, str]:
    config = current_log_config()
    return {
        "GOLEM_LOCAL_STACK_LOG_DIR": str(config.log_dir),
        "GOLEM_LOCAL_STACK_LOG_MAX_BYTES": str(config.max_bytes),
        "GOLEM_LOCAL_STACK_LOG_BACKUPS": str(config.backups),
        "PYTHONUNBUFFERED": "1",
    }


def service_log_env(prefix: str) -> dict[str, str]:
    config = current_log_config()
    return {
        **stack_log_env(),
        f"{prefix}_LOG_DIR": str(config.log_dir),
        f"{prefix}_LOG_MAX_BYTES": str(config.max_bytes),
        f"{prefix}_LOG_BACKUPS": str(config.backups),
    }


def merged_env(extra: dict[str, str]) -> dict[str, str]:
    env = os.environ.copy()
    env.update({key: str(value) for key, value in extra.items()})
    return env


def requestor_web_watch_env() -> dict[str, str]:
    """Use polling so Next.js detects edits reliably under the stack supervisor."""
    return {
        key: os.environ.get(key, default)
        for key, default in WEB_WATCH_ENV_DEFAULTS.items()
    }


def command_exists(command: str) -> bool:
    return shutil.which(command) is not None


def run_checked(command: list[str], cwd: Path = ROOT) -> None:
    log_setup(f"[setup] running: {' '.join(command)}")
    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        stdin=subprocess.DEVNULL,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
    )
    assert process.stdout is not None
    for line in process.stdout:
        log_service("setup", line.rstrip("\n"))
    returncode = process.wait()
    if returncode:
        raise subprocess.CalledProcessError(returncode, command)


def run_quiet(command: list[str], cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if _stack_logs is not None:
        _stack_logs.write("setup", f"[setup] checked: {' '.join(command)}")
        output = result.stdout.strip()
        if output:
            for line in output.splitlines():
                _stack_logs.write("setup", line)
    return result


def node_install_command(package_dir: str) -> list[str]:
    path = ROOT / package_dir
    if (path / "package-lock.json").exists():
        return ["npm", "--prefix", package_dir, "ci"]
    return ["npm", "--prefix", package_dir, "install"]


def ensure_command(command: str) -> None:
    if not command_exists(command):
        raise LocalStackError(f"Missing required command: {command}")


def ensure_port_free(host: str, port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError as exc:
            raise LocalStackError(f"Port {host}:{port} is already in use") from exc


def preflight(start_provider_desktop: bool) -> None:
    log_setup("[setup] checking required commands")
    for command in ("poetry", "node", "npm", "multipass"):
        log_setup(f"[setup] checking command: {command}")
        ensure_command(command)
    if start_provider_desktop:
        log_setup("[setup] checking command: cargo")
        ensure_command("cargo")

    log_setup("[setup] checking Multipass compatibility")
    multipass = run_quiet(["multipass", "version"])
    if multipass.returncode != 0:
        raise LocalStackError(
            "Multipass is installed but not usable:\n" + multipass.stdout.strip()
        )
    check_multipass_compatibility(multipass.stdout)

    for host, port in (
        (CENTRAL_HOST, CENTRAL_PORT),
        (PROVIDER_HOST, PROVIDER_PORT),
        (PORT_CHECKER_HOST, PORT_CHECKER_PORT),
        (REQUESTOR_HOST, REQUESTOR_PORT),
    ):
        log_setup(f"[setup] checking port: {host}:{port}")
        ensure_port_free(host, port)
    if start_provider_desktop:
        log_setup(
            f"[setup] checking port: {PROVIDER_DESKTOP_HOST}:{PROVIDER_DESKTOP_PORT}"
        )
        ensure_port_free(PROVIDER_DESKTOP_HOST, PROVIDER_DESKTOP_PORT)
    log_setup(f"[setup] checking port: {WEB_HOST}:{WEB_PORT}")
    ensure_port_free(WEB_HOST, WEB_PORT)


def rpc_call(rpc_url: str, method: str, params: list[object]) -> object:
    payload = json.dumps(
        {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
    ).encode("utf-8")
    request = urllib.request.Request(
        rpc_url,
        data=payload,
        headers={
            "content-type": "application/json",
            "user-agent": "vm-on-golem-local-stack/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise LocalStackError(
            f"{method} failed against {rpc_url}: HTTP {exc.code} {exc.reason}"
        ) from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise LocalStackError(f"{method} failed against {rpc_url}: {exc}") from exc
    if "error" in data:
        raise LocalStackError(f"{method} failed against {rpc_url}: {data['error']}")
    return data.get("result")


def find_working_l2_rpc(deployment: dict[str, str]) -> str:
    failures: list[str] = []
    address = deployment["stream_payment_address"]
    for rpc_url in L2_RPC_FALLBACK_URLS:
        try:
            chain_id = rpc_call(rpc_url, "eth_chainId", [])
            if str(chain_id).lower() != L2_CHAIN_ID_HEX:
                raise LocalStackError(
                    f"unexpected chain id {chain_id}; expected {L2_CHAIN_ID_HEX}"
                )
            code = str(rpc_call(rpc_url, "eth_getCode", [address, "latest"]))
            if not code or code == "0x":
                raise LocalStackError(f"no StreamPayment bytecode at {address}")
            return rpc_url
        except LocalStackError as exc:
            failures.append(f"{rpc_url}: {exc}")
    raise LocalStackError(
        "No working Ethereum Hoodi RPC found for local stack preflight:\n"
        + "\n".join(f"  - {failure}" for failure in failures)
    )


def load_l2_deployment() -> dict[str, str]:
    path = ROOT / "contracts" / "deployments" / "hoodi.json"
    try:
        data = json.loads(path.read_text())
        stream_payment = data["StreamPayment"]
        address = str(stream_payment["address"])
        glm_token = str(stream_payment.get("glmToken") or ZERO_ADDRESS)
        oracle = str(stream_payment.get("oracle") or "")
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise LocalStackError(f"Invalid Hoodi deployment metadata in {path}") from exc

    if not address or address == ZERO_ADDRESS:
        raise LocalStackError(
            f"Hoodi deployment metadata has no StreamPayment address: {path}"
        )

    return {
        "stream_payment_address": address,
        "glm_token_address": glm_token,
        "oracle_address": oracle,
    }


def check_l2_deployment(deployment: dict[str, str]) -> None:
    deployment["rpc_url"] = find_working_l2_rpc(deployment)


def check_multipass_compatibility(multipass_version: str) -> None:
    """Fail before startup for known-broken Apple Silicon Multipass builds."""
    if platform.system().lower() != "darwin" or platform.machine().lower() != "arm64":
        return

    release = platform.release().split(".", 1)[0]
    try:
        darwin_major = int(release)
    except ValueError:
        darwin_major = 0
    if darwin_major < 24:
        return

    multipass_path = shutil.which("multipass")
    if not multipass_path:
        return

    driver = run_quiet([multipass_path, "get", "local.driver"])
    driver_name = driver.stdout.strip() if driver.returncode == 0 else "qemu"
    if driver_name != "qemu":
        return

    first_multipass_line = (
        multipass_version.splitlines()[0] if multipass_version.splitlines() else ""
    )
    if "1.16.2+mac" not in first_multipass_line:
        return

    qemu_path = Path(multipass_path).resolve().parent / "qemu-system-aarch64"
    if not qemu_path.exists():
        return

    qemu = run_quiet([str(qemu_path), "--version"])
    if qemu.returncode != 0:
        return

    first_line = qemu.stdout.splitlines()[0] if qemu.stdout.splitlines() else ""
    version_tail = first_line.split("version", 1)[-1].strip()
    try:
        qemu_major = int(version_tail.split(".", 1)[0])
    except ValueError:
        qemu_major = 0

    if qemu_major and qemu_major < 10:
        raise LocalStackError(
            "This ARM mac has a known-broken Multipass/QEMU combination.\n"
            f"  multipass: {multipass_path}\n"
            f"  version: {first_multipass_line}\n"
            f"  driver: {driver_name}\n"
            f"  qemu: {first_line}\n\n"
            "The provider cannot launch VMs with this setup because it can fail "
            "before cloud-init with "
            "\"qemu-system-aarch64: Property 'host-arm-cpu.sme' not found\".\n\n"
            "Fix by downgrading to Multipass 1.16.1+mac, upgrading to a build "
            "with a fix, or using a supported non-QEMU driver. The local stack "
            "will not start until Multipass passes this provider compatibility "
            "check."
        )


def ensure_python_deps() -> None:
    for service in (
        "central-discovery-server",
        "port-checker-server",
        "provider-server",
        "requestor-server",
    ):
        log_setup(f"[setup] poetry install: {service}")
        run_checked(["poetry", "-C", service, "install", "--no-interaction"])


def ensure_node_deps(package_dir: str) -> None:
    path = ROOT / package_dir
    if (path / "node_modules").exists() and node_deps_satisfied(package_dir):
        return
    command = node_install_command(package_dir)
    log_setup(f"[setup] {' '.join(command)}")
    run_checked(command)


def node_deps_satisfied(package_dir: str) -> bool:
    check = run_quiet(["npm", "--prefix", package_dir, "ls", "--depth=0"])
    return check.returncode == 0


def ensure_workspace_node_deps(workspace: str) -> None:
    if (ROOT / "node_modules").exists() and workspace_node_deps_satisfied(workspace):
        return
    command = (
        ["npm", "ci"] if (ROOT / "package-lock.json").exists() else ["npm", "install"]
    )
    log_setup(f"[setup] {' '.join(command)}")
    run_checked(command)


def workspace_node_deps_satisfied(workspace: str) -> bool:
    check = run_quiet(["npm", "--workspace", workspace, "ls", "--depth=0"])
    return check.returncode == 0


def rust_target_triple() -> str:
    result = run_quiet(["rustc", "--print", "host-tuple"])
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()

    result = run_quiet(["rustc", "-Vv"])
    for line in result.stdout.splitlines():
        if line.startswith("host:"):
            return line.split(":", 1)[1].strip()
    raise LocalStackError("Could not determine Rust target triple")


def provider_sidecar_path() -> Path:
    suffix = ".exe" if os.name == "nt" else ""
    target = rust_target_triple()
    return (
        ROOT
        / "apps"
        / "provider-desktop"
        / "src-tauri"
        / "binaries"
        / f"golem-provider-{target}{suffix}"
    )


def provider_sidecar_is_stale(sidecar: Path) -> bool:
    if not sidecar.exists():
        return True
    source_paths = [
        ROOT / "provider-server" / "cli_runner.py",
        ROOT / "provider-server" / "pyproject.toml",
        ROOT / "provider-server" / "poetry.lock",
        ROOT / "scripts" / "build_provider_cli.py",
    ]
    source_paths.extend((ROOT / "provider-server" / "provider").rglob("*.py"))
    sidecar_mtime = sidecar.stat().st_mtime
    return any(
        path.stat().st_mtime > sidecar_mtime for path in source_paths if path.exists()
    )


def sync_existing_provider_tauri_sidecars(sidecar: Path) -> None:
    suffix = ".exe" if os.name == "nt" else ""
    for profile in ("debug", "release"):
        target = (
            ROOT
            / "apps"
            / "provider-desktop"
            / "src-tauri"
            / "target"
            / profile
            / f"golem-provider{suffix}"
        )
        if not target.exists():
            continue
        if target.stat().st_mtime >= sidecar.stat().st_mtime and (
            target.stat().st_size == sidecar.stat().st_size
        ):
            continue
        log_setup(f"[setup] syncing provider sidecar copy: {target}")
        shutil.copy2(sidecar, target)
        if os.name != "nt":
            target.chmod(0o755)


def ensure_provider_sidecar() -> None:
    sidecar = provider_sidecar_path()
    if not provider_sidecar_is_stale(sidecar):
        sync_existing_provider_tauri_sidecars(sidecar)
        return

    log_setup("[setup] staging provider desktop sidecar")
    result = run_quiet(
        [
            "poetry",
            "-C",
            "provider-server",
            "run",
            "python",
            "../scripts/build_provider_cli.py",
            "--onefile",
        ]
    )
    if result.returncode != 0:
        raise LocalStackError(
            "Could not stage provider desktop sidecar.\n"
            "Install PyInstaller in the provider Poetry env or run:\n"
            "  poetry -C provider-server run pip install pyinstaller\n"
            "Then retry make local.\n\n" + result.stdout.strip()
        )
    sync_existing_provider_tauri_sidecars(sidecar)


def stop_existing_provider_daemon() -> None:
    """Best-effort cleanup for a daemon left behind by provider desktop."""

    sidecar = provider_sidecar_path()
    command: list[str]
    if sidecar.exists():
        command = [str(sidecar), "stop", "--timeout", "5"]
    else:
        command = ["poetry", "-C", "provider-server", "run", "golem-provider", "stop"]

    log_setup("[setup] stopping any existing provider daemon")
    result = run_quiet(command)
    if result.returncode != 0:
        log_setup("[setup] provider daemon stop command did not complete cleanly")
        if result.stdout.strip():
            log_setup(result.stdout.strip())


def ensure_deps(skip_install: bool, start_provider_desktop: bool) -> None:
    if skip_install:
        return
    ensure_python_deps()
    ensure_node_deps("requestor-web")
    if start_provider_desktop:
        ensure_workspace_node_deps("@golem/provider-desktop")
        ensure_provider_sidecar()


def http_ok(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            return 200 <= response.status < 500
    except (OSError, urllib.error.URLError):
        return False


def central_has_provider() -> bool:
    try:
        with urllib.request.urlopen(
            f"{CENTRAL_API_URL}/advertisements", timeout=2
        ) as r:
            if r.status != 200:
                return False
            data = json.loads(r.read().decode("utf-8"))
            return isinstance(data, list) and len(data) > 0
    except (OSError, ValueError, urllib.error.URLError):
        return False


def stream_output(service: Service) -> None:
    assert service.process is not None
    assert service.process.stdout is not None
    for line in service.process.stdout:
        log_service(
            service.name,
            f"[{service.name}] {line.rstrip()}",
            write_service_log=service.write_service_log,
        )


def start_service(service: Service, timeout: int) -> None:
    log(f"[stack] starting {service.name}")
    log_service(service.name, f"[stack] starting {service.name}", echo=False)
    popen_kwargs: dict[str, object] = {}
    if os.name == "nt":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_kwargs["start_new_session"] = True

    service.process = subprocess.Popen(
        service.command,
        cwd=str(service.cwd),
        env=merged_env(service.env),
        stdin=subprocess.DEVNULL,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
        **popen_kwargs,
    )
    threading.Thread(target=stream_output, args=(service,), daemon=True).start()
    wait_ready(service, timeout)
    log_service(service.name, f"[stack] {service.name} is ready", echo=False)


def wait_ready(service: Service, timeout: int) -> None:
    if service.ready is None:
        time.sleep(1)
        if service.fatal and service.process and service.process.poll() is not None:
            log_service(
                service.name,
                f"[stack] {service.name} exited early with code {service.process.returncode}",
                echo=False,
            )
            raise LocalStackError(
                f"{service.name} exited early with code {service.process.returncode}"
            )
        return

    deadline = time.monotonic() + timeout
    log_service(
        service.name,
        f"[stack] waiting up to {timeout}s for {service.name} readiness",
        echo=False,
    )
    while time.monotonic() < deadline:
        if service.fatal and service.process and service.process.poll() is not None:
            log_service(
                service.name,
                f"[stack] {service.name} exited early with code {service.process.returncode}",
                echo=False,
            )
            raise LocalStackError(
                f"{service.name} exited early with code {service.process.returncode}"
            )
        if service.ready():
            log_service(
                service.name, f"[stack] {service.name} readiness passed", echo=False
            )
            return
        time.sleep(0.5)
    log_service(
        service.name,
        f"[stack] {service.name} did not become ready within {timeout}s",
        echo=False,
    )
    raise LocalStackError(f"{service.name} did not become ready within {timeout}s")


def stop_services(services: list[Service]) -> None:
    for service in reversed(services):
        process = service.process
        if process is None or process.poll() is not None:
            continue
        log(f"[stack] stopping {service.name}")
        log_service(service.name, f"[stack] stopping {service.name}", echo=False)
        terminate_process_tree(process)

    deadline = time.monotonic() + 10
    for service in reversed(services):
        process = service.process
        if process is None:
            continue
        remaining = max(0.1, deadline - time.monotonic())
        try:
            process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            log(f"[stack] killing {service.name}")
            log_service(service.name, f"[stack] killing {service.name}", echo=False)
            kill_process_tree(process)
            process.wait(timeout=5)


def terminate_process_tree(process: subprocess.Popen[str]) -> None:
    if os.name == "nt":
        process.terminate()
        return
    send_process_tree_signal(process, signal.SIGTERM)


def kill_process_tree(process: subprocess.Popen[str]) -> None:
    if os.name == "nt":
        process.kill()
        return
    send_process_tree_signal(process, signal.SIGKILL)


def send_process_tree_signal(process: subprocess.Popen[str], signum: int) -> None:
    if process.poll() is not None:
        return

    try:
        os.killpg(os.getpgid(process.pid), signum)
    except ProcessLookupError:
        return


def local_dirs() -> dict[str, Path]:
    dirs = {
        "central": LOCAL_DIR / "central-discovery",
        "provider": LOCAL_DIR / "provider",
        "requestor": LOCAL_DIR / "requestor",
        "logs": LOCAL_DIR / "logs",
    }
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return dirs


def build_services(
    deployment: dict[str, str],
    start_provider_desktop: bool,
) -> list[Service]:
    dirs = local_dirs()
    provider_dir = dirs["provider"]
    requestor_dir = dirs["requestor"]
    provider_env = {
        **service_log_env("GOLEM_PROVIDER"),
        "GOLEM_PROVIDER_SKIP_BOOTSTRAP": "1",
        "GOLEM_ENVIRONMENT": "development",
        "GOLEM_PROVIDER_NETWORK": "development",
        "GOLEM_PROVIDER_DISCOVERY_BACKEND": "central",
        "GOLEM_PROVIDER_DISCOVERY_URL": CENTRAL_URL,
        "GOLEM_PROVIDER_PAYMENTS_NETWORK": PAYMENTS_NETWORK,
        "GOLEM_PROVIDER_L2_RPC_URL": deployment.get("rpc_url", L2_RPC_URL),
        "GOLEM_PROVIDER_L2_FAUCET_URL": L2_FAUCET_URL,
        "GOLEM_PROVIDER_STREAM_PAYMENT_ADDRESS": deployment["stream_payment_address"],
        "GOLEM_PROVIDER_GLM_TOKEN_ADDRESS": deployment["glm_token_address"],
        "GOLEM_PROVIDER_ARKIV_FAUCET_ENABLED": "false",
        "GOLEM_PROVIDER_ARKIV_RPC_URL": ARKIV_RPC_URL,
        "GOLEM_PROVIDER_ARKIV_WS_URL": ARKIV_WS_URL,
        "GOLEM_PROVIDER_HOST": PROVIDER_BIND_HOST,
        "GOLEM_PROVIDER_PORT": str(PROVIDER_PORT),
        "GOLEM_PROVIDER_PUBLIC_IP": "auto",
        "GOLEM_PROVIDER_SECURE_SETUP_IN_DEVELOPMENT": "false",
        "GOLEM_PROVIDER_SHOW_JSON_LOGS": "1",
        "GOLEM_PROVIDER_PORT_CHECK_TLS_URL": PORT_CHECKER_URL,
        "GOLEM_PROVIDER_PORT_CHECK_REQUEST_TIMEOUT": "5",
        "GOLEM_PROVIDER_ACME_ENV": "staging",
        "GOLEM_PROVIDER_ETHEREUM_KEY_DIR": str(provider_dir / "keys"),
        "GOLEM_PROVIDER_SSH_KEY_DIR": str(provider_dir / "ssh"),
        "GOLEM_PROVIDER_VM_DATA_DIR": str(provider_dir / "vms"),
        "GOLEM_PROVIDER_CLOUD_INIT_DIR": str(provider_dir / "cloud-init"),
        "GOLEM_PROVIDER_PROXY_STATE_DIR": str(provider_dir / "proxy"),
        "GOLEM_PROVIDER_CERT_DIR": str(provider_dir / "certs"),
        "GOLEM_PROVIDER_STOP_VMS_ON_EXIT": "0",
    }

    services = [
        Service(
            name="central-discovery",
            command=[
                "poetry",
                "-C",
                "central-discovery-server",
                "run",
                "golem-central-discovery",
            ],
            env={
                **service_log_env("GOLEM_CENTRAL_DISCOVERY"),
                "GOLEM_CENTRAL_DISCOVERY_HOST": CENTRAL_HOST,
                "GOLEM_CENTRAL_DISCOVERY_PORT": str(CENTRAL_PORT),
                "GOLEM_CENTRAL_DISCOVERY_DATABASE_DIR": str(dirs["central"]),
                "GOLEM_CENTRAL_DISCOVERY_DATABASE_NAME": "local.db",
                "GOLEM_CENTRAL_DISCOVERY_DEBUG": "false",
            },
            ready=lambda: http_ok(f"{CENTRAL_URL}/health"),
        ),
        Service(
            name="port-checker",
            command=[
                "poetry",
                "-C",
                "port-checker-server",
                "run",
                "port-checker",
            ],
            env={
                **service_log_env("PORT_CHECKER"),
                "GOLEM_ENVIRONMENT": "development",
                "PORT_CHECKER_HOST": PORT_CHECKER_HOST,
                "PORT_CHECKER_PORT": str(PORT_CHECKER_PORT),
                "PORT_CHECKER_EXPECTED_NETWORK": "development",
                "PORT_CHECK_RETRIES": "1",
                "PORT_CHECK_TIMEOUT": "3",
                "PORT_CHECK_RETRY_DELAY": "0.25",
            },
            ready=lambda: http_ok(f"{PORT_CHECKER_URL}/health"),
        ),
    ]

    if not start_provider_desktop:
        services.extend(
            [
                Service(
                    name="provider",
                    command=[
                        "poetry",
                        "-C",
                        "provider-server",
                        "run",
                        "golem-provider",
                        "start",
                        "--network",
                        "development",
                        "--no-verify-port",
                        "--keep-vms-on-exit",
                    ],
                    env=provider_env,
                    ready=lambda: http_ok(f"{PROVIDER_API_URL}/provider/info"),
                ),
                Service(
                    name="central-advertisement",
                    command=[sys.executable, "-c", "import time; time.sleep(3600)"],
                    env=stack_log_env(),
                    ready=central_has_provider,
                ),
            ]
        )

    services.append(
        Service(
            name="requestor-api",
            command=[
                "poetry",
                "-C",
                "requestor-server",
                "run",
                "golem",
                "server",
                "api",
                "--host",
                REQUESTOR_HOST,
                "--port",
                str(REQUESTOR_PORT),
                "--reload",
            ],
            env={
                **service_log_env("GOLEM_REQUESTOR"),
                "GOLEM_ENVIRONMENT": "development",
                "GOLEM_REQUESTOR_NETWORK": "development",
                "GOLEM_REQUESTOR_DISCOVERY_BACKEND": "central",
                "GOLEM_REQUESTOR_DISCOVERY_URL": CENTRAL_URL,
                "GOLEM_REQUESTOR_PAYMENTS_NETWORK": PAYMENTS_NETWORK,
                "GOLEM_REQUESTOR_L2_RPC_URL": deployment.get("rpc_url", L2_RPC_URL),
                "GOLEM_REQUESTOR_L2_FAUCET_URL": L2_FAUCET_URL,
                "GOLEM_REQUESTOR_STREAM_PAYMENT_ADDRESS": deployment[
                    "stream_payment_address"
                ],
                "GOLEM_REQUESTOR_GLM_TOKEN_ADDRESS": deployment["glm_token_address"],
                "GOLEM_REQUESTOR_ARKIV_RPC_URL": ARKIV_RPC_URL,
                "GOLEM_REQUESTOR_ARKIV_WS_URL": ARKIV_WS_URL,
                "GOLEM_REQUESTOR_BASE_DIR": str(requestor_dir),
                "GOLEM_REQUESTOR_DB_PATH": str(requestor_dir / "vms.db"),
            },
            ready=lambda: http_ok(f"{REQUESTOR_API_URL}/settings"),
        )
    )

    requestor_ui_env = {
        **stack_log_env(),
        "GOLEM_ENVIRONMENT": "development",
        "NEXT_PUBLIC_GOLEM_ENVIRONMENT": "development",
        "NEXT_PUBLIC_DISCOVERY_MODE": "central",
        "NEXT_PUBLIC_DISCOVERY_API_URL": CENTRAL_API_URL,
        "NEXT_PUBLIC_STREAM_PAYMENT_ADDRESS": deployment["stream_payment_address"],
        "NEXT_PUBLIC_GLM_TOKEN_ADDRESS": deployment["glm_token_address"],
        "NEXT_PUBLIC_EVM_CHAIN_ID": L2_CHAIN_ID_HEX,
        "NEXT_PUBLIC_EVM_CHAIN_NAME": "Ethereum Hoodi",
        "NEXT_PUBLIC_EVM_RPC_URL": deployment.get("rpc_url", L2_RPC_URL),
        "NEXT_PUBLIC_EVM_EXPLORER_URL": L2_EXPLORER_URL,
        "NEXT_PUBLIC_ARKIV_DEV_RPC_URL": ARKIV_RPC_URL,
        "NEXT_PUBLIC_ARKIV_DEV_WS_URL": ARKIV_WS_URL,
    }

    services.append(
        Service(
            name="requestor-web",
            command=[
                "npm",
                "--prefix",
                "requestor-web",
                "run",
                "dev",
                "--",
                "--hostname",
                WEB_HOST,
                "--port",
                str(WEB_PORT),
            ],
            env={
                **requestor_ui_env,
                **requestor_web_watch_env(),
            },
            ready=lambda: http_ok(WEB_URL),
        )
    )

    if start_provider_desktop:
        provider_log_path = current_log_config().log_dir / "provider.log"
        services.append(
            Service(
                name="provider",
                command=[
                    sys.executable,
                    "-u",
                    "-c",
                    textwrap.dedent(
                        """
                        import pathlib
                        import sys
                        import time

                        path = pathlib.Path(sys.argv[1])
                        offset = 0
                        while True:
                            try:
                                if path.exists():
                                    size = path.stat().st_size
                                    if size < offset:
                                        offset = 0
                                    with path.open("r", encoding="utf-8", errors="replace") as handle:
                                        handle.seek(offset)
                                        while True:
                                            line = handle.readline()
                                            if not line:
                                                offset = handle.tell()
                                                break
                                            print(line.rstrip("\\n"), flush=True)
                            except Exception as exc:
                                print(f"[provider-log-tail] {exc}", flush=True)
                            time.sleep(0.25)
                        """
                    ),
                    str(provider_log_path),
                ],
                env=stack_log_env(),
                ready=None,
                fatal=False,
                write_service_log=False,
            )
        )
        services.append(
            Service(
                name="provider-desktop",
                command=[
                    "npm",
                    "--workspace",
                    "@golem/provider-desktop",
                    "run",
                    "dev",
                ],
                env={
                    **provider_env,
                    "GOLEM_ENVIRONMENT": "development",
                    "TAURI_PROVIDER_API_URL": PROVIDER_API_URL,
                },
                ready=lambda: http_ok(PROVIDER_DESKTOP_URL),
            )
        )

    return services


def run_stack(args: argparse.Namespace) -> int:
    running: list[Service] = []
    checkpoint: Service | None = None
    log_config = LogConfig(
        log_dir=Path(args.log_dir),
        max_bytes=args.log_max_bytes,
        backups=args.log_backups,
    )
    configure_stack_logging(log_config)
    log_setup(f"[stack] logs: {log_config.log_dir}")

    try:
        start_provider_desktop = not args.no_provider_desktop
        if start_provider_desktop:
            stop_existing_provider_daemon()
        preflight(start_provider_desktop)
        deployment = load_l2_deployment()
        if not args.skip_chain_check:
            check_l2_deployment(deployment)
        ensure_deps(args.skip_install, start_provider_desktop)

        services = build_services(
            deployment=deployment,
            start_provider_desktop=start_provider_desktop,
        )

        def handle_signal(signum: int, _frame) -> None:
            raise KeyboardInterrupt

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

        for service in services:
            if service.name == "central-advertisement":
                checkpoint = service
                log("[stack] waiting for provider advertisement in central discovery")
                log_service(
                    service.name,
                    "[stack] waiting for provider advertisement in central discovery",
                    echo=False,
                )
                wait_ready(service, args.timeout)
                continue
            running.append(service)
            start_service(service, args.timeout)

        log("")
        log("Local stack is ready:")
        log(f"  Requestor web:      {WEB_URL}")
        log(f"  Central discovery:  {CENTRAL_API_URL}")
        if start_provider_desktop:
            log("  Provider desktop:   native Tauri app")
            log("  Provider API:       started from provider desktop")
        else:
            log(f"  Provider API:       {PROVIDER_API_URL}")
        log(f"  Port checker:       {PORT_CHECKER_URL}")
        log(f"  Requestor API:      {REQUESTOR_API_URL}")
        log(f"  Payments network:   {PAYMENTS_NETWORK} ({L2_CHAIN_ID_HEX})")
        log(f"  Payments RPC:       {deployment.get('rpc_url', L2_RPC_URL)}")
        log(f"  StreamPayment:      {deployment['stream_payment_address']}")
        log(f"  Logs:               {log_config.log_dir}")
        log("")
        log("Press Ctrl+C to stop the stack.")

        if not args.no_open:
            webbrowser.open(WEB_URL)

        while True:
            for service in running:
                process = service.process
                if service.fatal and process is not None and process.poll() is not None:
                    raise LocalStackError(
                        f"{service.name} exited with code {process.returncode}"
                    )
            time.sleep(1)
    except KeyboardInterrupt:
        log("")
        log("[stack] shutdown requested")
        return 0
    except LocalStackError as exc:
        log(f"[stack] error: {exc}")
        log(f"[stack] logs: {log_config.log_dir}")
        return 1
    except subprocess.CalledProcessError as exc:
        log(f"[stack] command failed with code {exc.returncode}: {' '.join(exc.cmd)}")
        log(f"[stack] logs: {log_config.log_dir}")
        return 1
    finally:
        if checkpoint and checkpoint.process is not None:
            running.append(checkpoint)
        stop_services(running)
        if _stack_logs is not None:
            _stack_logs.close()


def parse_args(argv: list[str]) -> argparse.Namespace:
    default_logs = default_log_config()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-open", action="store_true", help="Do not open the web UI")
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="Skip Poetry/npm dependency installation checks",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=90,
        help="Seconds to wait for each service readiness check",
    )
    parser.add_argument(
        "--skip-chain-check",
        action="store_true",
        help="Skip Arkiv L2 chain and StreamPayment deployment validation",
    )
    parser.add_argument(
        "--no-provider-desktop",
        action="store_true",
        help="Do not start the provider desktop Tauri app",
    )
    parser.add_argument(
        "--log-dir",
        default=str(default_logs.log_dir),
        help="Directory for rotating local stack logs",
    )
    parser.add_argument(
        "--log-max-bytes",
        type=int,
        default=default_logs.max_bytes,
        help="Maximum bytes per log file before rotation",
    )
    parser.add_argument(
        "--log-backups",
        type=int,
        default=default_logs.backups,
        help="Number of rotated log files to retain",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    return run_stack(parse_args(argv or sys.argv[1:]))


if __name__ == "__main__":
    raise SystemExit(main())
