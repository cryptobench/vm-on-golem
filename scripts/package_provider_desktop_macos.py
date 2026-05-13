#!/usr/bin/env python3
"""Wrap the Tauri macOS app in a pkg that conditionally installs Multipass."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_NAME = "Golem Provider.app"
DESKTOP_DIR = ROOT / "apps" / "provider-desktop"
TAURI_DIR = DESKTOP_DIR / "src-tauri"
DEFAULT_APP = TAURI_DIR / "target" / "release" / "bundle" / "macos" / APP_NAME
DEFAULT_VENDOR = TAURI_DIR / "vendor" / "multipass"
DEFAULT_POSTINSTALL = TAURI_DIR / "installer" / "macos" / "postinstall"


def provider_desktop_version() -> str:
    with (DESKTOP_DIR / "package.json").open("r", encoding="utf-8") as fh:
        return json.load(fh)["version"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", type=Path, default=DEFAULT_APP)
    parser.add_argument("--vendor-dir", type=Path, default=DEFAULT_VENDOR)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=TAURI_DIR / "target" / "release" / "bundle" / "pkg",
    )
    parser.add_argument("--version", default=provider_desktop_version())
    parser.add_argument(
        "--signing-identity",
        default=os.environ.get("APPLE_INSTALLER_SIGNING_IDENTITY", ""),
    )
    args = parser.parse_args()

    if not args.app.exists():
        raise SystemExit(f"Tauri app bundle not found: {args.app}")
    multipass_pkgs = sorted(args.vendor_dir.glob("multipass-*.pkg"))
    if len(multipass_pkgs) != 1:
        raise SystemExit(f"Expected one vendored Multipass pkg in {args.vendor_dir}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    output = args.out_dir / f"Golem Provider_{args.version}_universal.pkg"

    with tempfile.TemporaryDirectory(prefix="provider-desktop-pkg-") as tmp:
        tmp_dir = Path(tmp)
        root = tmp_dir / "root"
        scripts = tmp_dir / "scripts"
        app_dest = root / "Applications" / APP_NAME
        multipass_dest = (
            root
            / "Library"
            / "Application Support"
            / "Golem Provider"
            / "multipass"
            / multipass_pkgs[0].name
        )
        app_dest.parent.mkdir(parents=True, exist_ok=True)
        multipass_dest.parent.mkdir(parents=True, exist_ok=True)
        scripts.mkdir(parents=True, exist_ok=True)

        shutil.copytree(args.app, app_dest, symlinks=True)
        shutil.copy2(multipass_pkgs[0], multipass_dest)
        shutil.copy2(DEFAULT_POSTINSTALL, scripts / "postinstall")
        os.chmod(scripts / "postinstall", 0o755)

        command = [
            "pkgbuild",
            "--root",
            str(root),
            "--scripts",
            str(scripts),
            "--identifier",
            "network.golem.provider",
            "--version",
            args.version,
        ]
        if args.signing_identity:
            command.extend(["--sign", args.signing_identity])
        command.append(str(output))
        print("Running:", " ".join(command))
        subprocess.run(command, check=True)

    print(f"Built macOS pkg -> {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
