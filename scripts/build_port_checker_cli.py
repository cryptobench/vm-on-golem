#!/usr/bin/env python3
"""
Builds a standalone port-checker binary using PyInstaller and places it
under apps/requestor-desktop/src-tauri/binaries/ with the target-triple suffix
required by Tauri sidecars.

Requires: Python 3.10+, pyinstaller installed in the active env.

Usage:
  python scripts/build_port_checker_cli.py [--onefile]
"""

import argparse
import os
import platform
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "port-checker-server" / "run.py"
TAURI_BINARIES = (
    ROOT / "apps" / "requestor-desktop" / "src-tauri" / "binaries"
)


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


def ensure_pyinstaller() -> None:
    try:
        import PyInstaller  # noqa: F401
    except Exception as exc:
        raise SystemExit(
            "PyInstaller not found. Install with: pip install pyinstaller"
        ) from exc


def build(onefile: bool) -> Path:
    ensure_pyinstaller()
    name = "golem-port-checker"
    args = [
        "pyinstaller",
        "-n",
        name,
        "--clean",
    ]
    if onefile:
        args.append("-F")
    if platform.system().lower().startswith("windows"):
        args.append("-w")
    args.append(str(ENTRY))
    print("Running:", " ".join(args))
    subprocess.run(args, cwd=str(ROOT), check=True)

    dist_dir = ROOT / "dist" / name
    if onefile:
        dist_dir = ROOT / "dist"
    suffix = ".exe" if platform.system().lower().startswith("windows") else ""
    exe = dist_dir / f"{name}{suffix}"
    if not exe.exists():
        raise SystemExit(f"Build artifact not found: {exe}")
    return exe


def stage(exe_path: Path) -> Path:
    target = detect_target_triple()
    TAURI_BINARIES.mkdir(parents=True, exist_ok=True)
    suffix = ".exe" if platform.system().lower().startswith("windows") else ""
    out = TAURI_BINARIES / f"golem-port-checker-{target}{suffix}"
    shutil.copy2(exe_path, out)
    try:
        os.chmod(out, 0o755)
    except Exception:
        pass
    print(f"Staged port-checker -> {out}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--onefile", action="store_true", help="Build single-file binary")
    args = parser.parse_args()
    exe = build(onefile=args.onefile)
    stage(exe)


if __name__ == "__main__":
    main()
