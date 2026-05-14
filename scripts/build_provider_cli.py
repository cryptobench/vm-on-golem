#!/usr/bin/env python3
"""
Builds a standalone provider CLI binary using PyInstaller and places it
under apps/provider-desktop/src-tauri/binaries/ with the target-triple suffix
required by Tauri sidecars.

Requires: Python 3.11, pyinstaller installed in the active env.

Usage:
  python scripts/build_provider_cli.py [--onefile]
"""

import argparse
import importlib.machinery
import importlib.util
import os
import platform
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "provider-server" / "cli_runner.py"
TAURI_BINARIES = ROOT / "apps" / "provider-desktop" / "src-tauri" / "binaries"
HIDDEN_IMPORTS = [
    "dependency_injector.containers",
    "dependency_injector.errors",
    "dependency_injector.providers",
    "dependency_injector.wiring",
    "miniupnpc",
]
COLLECT_ALL_MODULES = [
    # eth-account loads PyCryptodome native modules dynamically. Without the
    # collected package, the daemon child can crash before opening the API.
    "Crypto",
]
EXTENSION_BINARY_MODULES = [
    # PyInstaller's collect-all does not pick up PyCryptodome's _*.abi3.so
    # files as binaries on macOS/Linux because they do not match lib*.so.
    "Crypto",
]


def detect_target_triple() -> str:
    try:
        result = subprocess.run(
            ["rustc", "--print", "host-tuple"],
            check=True,
            capture_output=True,
            text=True,
        )
        target = result.stdout.strip()
        if target:
            return target
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    result = subprocess.run(
        ["rustc", "-Vv"],
        check=True,
        capture_output=True,
        text=True,
    )
    for line in result.stdout.splitlines():
        if line.startswith("host:"):
            return line.split(":", 1)[1].strip()
    raise SystemExit("Could not determine Rust target triple for Tauri sidecar")


def ensure_pyinstaller():
    try:
        import PyInstaller  # noqa: F401
    except Exception:
        raise SystemExit("PyInstaller not found. Install with: pip install pyinstaller")


def collect_extension_binaries(package: str) -> list[tuple[Path, str]]:
    spec = importlib.util.find_spec(package)
    if spec is None or spec.submodule_search_locations is None:
        raise SystemExit(f"Package not found: {package}")

    suffixes = tuple(importlib.machinery.EXTENSION_SUFFIXES)
    binaries: list[tuple[Path, str]] = []
    seen: set[tuple[str, str]] = set()
    for package_dir_raw in spec.submodule_search_locations:
        package_dir = Path(package_dir_raw)
        package_root = package_dir.parent
        for path in sorted(package_dir.rglob("*")):
            if not path.is_file() or not path.name.endswith(suffixes):
                continue
            dest = str(path.parent.relative_to(package_root))
            key = (str(path), dest)
            if key in seen:
                continue
            seen.add(key)
            binaries.append((path, dest))
    return binaries


def build(onefile: bool) -> Path:
    ensure_pyinstaller()
    name = "golem-provider"
    args = [
        "pyinstaller",
        "-n",
        name,
        "--clean",
    ]
    for module in HIDDEN_IMPORTS:
        args.extend(["--hidden-import", module])
    for module in COLLECT_ALL_MODULES:
        args.extend(["--collect-all", module])
    for module in EXTENSION_BINARY_MODULES:
        for source, dest in collect_extension_binaries(module):
            args.extend(["--add-binary", f"{source}{os.pathsep}{dest}"])
    if onefile:
        args.append("-F")
    # Reduce console popups on Windows
    if platform.system().lower().startswith("windows"):
        args.append("-w")
    args.append(str(ENTRY))
    print("Running:", " ".join(args))
    subprocess.run(args, cwd=str(ROOT), check=True)
    dist_dir = ROOT / "dist" / name
    if onefile:
        # in onefile, artifact is dist/golem-provider(.exe)
        dist_dir = ROOT / "dist"
    exe = dist_dir / (
        name + (".exe" if platform.system().lower().startswith("windows") else "")
    )
    if not exe.exists():
        raise SystemExit(f"Build artifact not found: {exe}")
    return exe


def stage(exe_path: Path) -> Path:
    target = detect_target_triple()
    target_dir = TAURI_BINARIES
    target_dir.mkdir(parents=True, exist_ok=True)
    suffix = ".exe" if platform.system().lower().startswith("windows") else ""
    out = target_dir / f"golem-provider-{target}{suffix}"
    shutil.copy2(exe_path, out)
    # Ensure executable on POSIX
    try:
        os.chmod(out, 0o755)
    except Exception:
        pass
    print(f"Staged CLI -> {out}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--onefile", action="store_true", help="Build single-file binary")
    args = ap.parse_args()
    exe = build(onefile=args.onefile)
    stage(exe)


if __name__ == "__main__":
    main()
