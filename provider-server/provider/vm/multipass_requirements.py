import json
import os
import platform
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Sequence

DEFAULT_MIN_VERSION = "1.13.0"
DEFAULT_PREFERRED_VERSION = "1.16.2"


@dataclass(frozen=True)
class MultipassRequirementResult:
    installed: bool
    path: str | None
    version: str | None
    source: str | None
    compatible: bool
    daemon_running: bool
    driver: str | None
    action_required: str
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)


RunCommand = Callable[
    [Sequence[str], int],
    subprocess.CompletedProcess[str],
]


def run_subprocess(
    command: Sequence[str], timeout: int
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def detect_multipass_binary(explicit_path: str | None = None) -> str | None:
    if explicit_path:
        return explicit_path

    binary_name = (
        "multipass.exe" if platform.system().lower() == "windows" else "multipass"
    )
    system = platform.system().lower()
    search_paths: list[str] = []

    if system == "linux":
        search_paths = ["/snap/bin", "/usr/local/bin", "/usr/bin"]
    elif system == "darwin":
        search_paths = [
            "/Library/Application Support/com.canonical.multipass/bin",
            "/opt/homebrew/bin",
            "/usr/local/bin",
            "/opt/local/bin",
        ]
    elif system == "windows":
        search_paths = [
            os.path.join(os.path.expandvars(r"%ProgramFiles%"), "Multipass", "bin"),
            os.path.join(
                os.path.expandvars(r"%ProgramFiles(x86)%"), "Multipass", "bin"
            ),
            os.path.join(os.path.expandvars(r"%LocalAppData%"), "Multipass", "bin"),
        ]

    for directory in search_paths:
        candidate = os.path.join(directory, binary_name)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate

    return shutil.which(binary_name)


def check_multipass_requirements(
    *,
    explicit_path: str | None = None,
    min_version: str = DEFAULT_MIN_VERSION,
    preferred_version: str = DEFAULT_PREFERRED_VERSION,
    blocked_versions: set[str] | None = None,
    run_command: RunCommand = run_subprocess,
    run_daemon_check: bool = True,
    progress: Callable[[str], None] | None = None,
) -> MultipassRequirementResult:
    if progress:
        progress("locating Multipass binary")
    path = detect_multipass_binary(explicit_path)
    blocked_versions = blocked_versions or set()
    if not path:
        return MultipassRequirementResult(
            installed=False,
            path=None,
            version=None,
            source=None,
            compatible=False,
            daemon_running=False,
            driver=None,
            action_required="install",
            error="Multipass binary was not found",
        )

    if not os.path.isfile(path) and not shutil.which(path):
        return MultipassRequirementResult(
            installed=False,
            path=path,
            version=None,
            source=_source_for_path(path),
            compatible=False,
            daemon_running=False,
            driver=None,
            action_required="install",
            error=f"Configured Multipass binary does not exist: {path}",
        )

    if progress:
        progress("reading Multipass version")
    version_result = _run_checked(run_command, [path, "version"], timeout=5)
    version = _parse_version(version_result.stdout or version_result.stderr)
    if version_result.returncode != 0 or not version:
        return MultipassRequirementResult(
            installed=True,
            path=path,
            version=version,
            source=_source_for_path(path),
            compatible=False,
            daemon_running=False,
            driver=None,
            action_required="repair",
            error=(
                version_result.stderr or version_result.stdout or "version check failed"
            ).strip(),
        )

    if progress:
        progress("reading Multipass driver")
    driver = _read_driver(path, run_command)
    if progress and run_daemon_check:
        progress("checking Multipass daemon response")
    daemon_running = (
        _daemon_is_running(path, run_command) if run_daemon_check else False
    )

    if progress:
        progress("validating Multipass version compatibility")
    incompatible_reason = _version_incompatibility(
        version=version,
        min_version=min_version,
        preferred_version=preferred_version,
        blocked_versions=blocked_versions,
    )
    if incompatible_reason:
        return MultipassRequirementResult(
            installed=True,
            path=path,
            version=version,
            source=_source_for_path(path),
            compatible=False,
            daemon_running=daemon_running,
            driver=driver,
            action_required="upgrade",
            error=incompatible_reason,
        )

    if progress:
        progress("validating host virtualization compatibility")
    try:
        check_host_virtualization_compatibility(path, run_command=run_command)
    except MultipassCompatibilityError as exc:
        return MultipassRequirementResult(
            installed=True,
            path=path,
            version=version,
            source=_source_for_path(path),
            compatible=False,
            daemon_running=daemon_running,
            driver=driver,
            action_required="repair",
            error=str(exc),
        )

    if run_daemon_check and not daemon_running:
        return MultipassRequirementResult(
            installed=True,
            path=path,
            version=version,
            source=_source_for_path(path),
            compatible=False,
            daemon_running=False,
            driver=driver,
            action_required="repair",
            error="Multipass daemon is not responding",
        )

    if progress:
        progress("host requirements ready")
    return MultipassRequirementResult(
        installed=True,
        path=path,
        version=version,
        source=_source_for_path(path),
        compatible=True,
        daemon_running=daemon_running,
        driver=driver,
        action_required="none",
        error=None,
    )


class MultipassCompatibilityError(RuntimeError):
    pass


def check_host_virtualization_compatibility(
    multipass_path: str,
    *,
    run_command: RunCommand = run_subprocess,
) -> None:
    system = platform.system().lower()
    if system == "linux":
        _check_linux_kvm_support(run_command)
        return

    if system != "darwin" or platform.machine().lower() != "arm64":
        return

    darwin_major = _safe_int(platform.release().split(".", 1)[0], 0)
    if darwin_major < 24:
        return

    driver_result = _run_checked(
        run_command, [multipass_path, "get", "local.driver"], timeout=5
    )
    driver = driver_result.stdout.strip() if driver_result.returncode == 0 else "qemu"
    if driver != "qemu":
        return

    version_result = _run_checked(run_command, [multipass_path, "version"], timeout=5)
    first_multipass_line = _first_line(version_result.stdout)
    if "1.16.2+mac" not in first_multipass_line:
        return

    bundled_qemu = Path(multipass_path).resolve().parent / "qemu-system-aarch64"
    if not bundled_qemu.exists():
        return

    qemu_result = _run_checked(run_command, [str(bundled_qemu), "--version"], timeout=5)
    if qemu_result.returncode != 0:
        return

    qemu_line = _first_line(qemu_result.stdout)
    major = _safe_int(qemu_line.split("version", 1)[-1].split(".", 1)[0], 0)
    if major and major < 10:
        raise MultipassCompatibilityError(
            "This Multipass installation uses "
            f"{first_multipass_line} with the qemu driver and bundled "
            f"QEMU {qemu_line} on Apple Silicon/macOS. This combination is "
            "known to fail before cloud-init with "
            "\"qemu-system-aarch64: Property 'host-arm-cpu.sme' not found\". "
            "Downgrade to Multipass 1.16.1+mac, upgrade to a build with a "
            "fix, use a supported non-QEMU driver, or run the provider on a "
            "Linux host."
        )


def _check_linux_kvm_support(run_command: RunCommand) -> None:
    exists_result = _run_checked(
        run_command, ["sh", "-c", "test -c /dev/kvm"], timeout=5
    )
    if exists_result.returncode != 0:
        raise MultipassCompatibilityError(
            "KVM support is not enabled on this Linux host: /dev/kvm is missing "
            "or is not a character device. Ensure the CPU supports virtualization, "
            "enable virtualization in BIOS/UEFI, and load the KVM kernel modules."
        )


def _run_checked(
    run_command: RunCommand,
    command: Sequence[str],
    *,
    timeout: int,
) -> subprocess.CompletedProcess[str]:
    try:
        return run_command(command, timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(
            args=list(command),
            returncode=1,
            stdout="",
            stderr=str(exc),
        )


def _daemon_is_running(path: str, run_command: RunCommand) -> bool:
    result = _run_checked(run_command, [path, "list", "--format", "json"], timeout=8)
    return result.returncode == 0


def _read_driver(path: str, run_command: RunCommand) -> str | None:
    result = _run_checked(run_command, [path, "get", "local.driver"], timeout=5)
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _parse_version(output: str) -> str | None:
    match = re.search(r"multipass\s+([0-9]+(?:\.[0-9]+){1,2}(?:[+\-.][^\s]+)?)", output)
    if match:
        return match.group(1)
    match = re.search(r"([0-9]+(?:\.[0-9]+){1,2}(?:[+\-.][^\s]+)?)", output)
    return match.group(1) if match else None


def _version_incompatibility(
    *,
    version: str,
    min_version: str,
    preferred_version: str,
    blocked_versions: set[str],
) -> str | None:
    if version in blocked_versions:
        return f"Multipass {version} is blocked for this provider build"
    if _version_tuple(version) < _version_tuple(min_version):
        return (
            f"Multipass {version} is below the minimum supported version "
            f"{min_version}; install {preferred_version} or newer"
        )
    return None


def _version_tuple(version: str) -> tuple[int, int, int]:
    release = version.split("+", 1)[0].split("-", 1)[0]
    parts = [_safe_int(part, 0) for part in release.split(".")]
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def _source_for_path(path: str) -> str:
    normalized = path.replace("\\", "/").lower()
    if normalized.startswith("/snap/") or "/snap/" in normalized:
        return "snap"
    if "homebrew" in normalized:
        return "homebrew"
    if "multipass/bin" in normalized or "/multipass/bin" in normalized:
        return "canonical-installer"
    if normalized.endswith("/multipass") or normalized.endswith("/multipass.exe"):
        return "path"
    return "unknown"


def _first_line(value: str) -> str:
    return value.splitlines()[0] if value.splitlines() else ""


def _safe_int(value: str, default: int) -> int:
    try:
        return int(value.strip())
    except (AttributeError, ValueError):
        return default
