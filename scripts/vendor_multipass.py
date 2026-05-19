#!/usr/bin/env python3
"""Vendor the pinned Multipass installer asset for provider desktop packaging."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "apps" / "provider-desktop" / "multipass.lock.json"
DEFAULT_OUT_DIR = (
    ROOT / "apps" / "provider-desktop" / "src-tauri" / "vendor" / "multipass"
)


def normalize_platform(value: str) -> str:
    raw = value.lower()
    if raw in {"win32", "windows"}:
        return "windows"
    if raw in {"darwin", "mac", "macos"}:
        return "darwin"
    if raw in {"linux"}:
        return "linux"
    raise SystemExit(f"Unsupported platform: {value}")


def normalize_arch(value: str) -> str:
    raw = value.lower()
    if raw in {"amd64", "x64", "x86_64"}:
        return "x86_64"
    if raw in {"arm64", "aarch64"}:
        return "aarch64"
    if raw in {"universal"}:
        return "universal"
    raise SystemExit(f"Unsupported architecture: {value}")


def current_platform() -> str:
    return normalize_platform(platform.system())


def current_arch() -> str:
    return normalize_arch(platform.machine())


def load_manifest(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def select_asset(
    manifest: dict[str, Any], target_platform: str, target_arch: str
) -> dict[str, Any]:
    candidates = [
        asset
        for asset in manifest["assets"]
        if asset["platform"] == target_platform
        and asset["arch"] in {target_arch, "universal"}
    ]
    if not candidates:
        raise SystemExit(
            f"No Multipass asset for platform={target_platform} arch={target_arch}"
        )
    return candidates[0]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_sha256(path: Path, expected: str) -> None:
    actual = sha256_file(path)
    if actual != expected:
        raise SystemExit(
            f"SHA256 mismatch for {path}: expected {expected}, got {actual}"
        )


def selected_version(manifest: dict[str, Any], asset: dict[str, Any]) -> str:
    return asset.get("version", manifest["preferred_version"])


def download_url(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=180) as response, dest.open("wb") as fh:
        shutil.copyfileobj(response, fh)


def vendor_direct(asset: dict[str, Any], out_dir: Path) -> list[Path]:
    dest = out_dir / asset["file_name"]
    print(f"Downloading {asset['asset_url']} -> {dest}")
    download_url(asset["asset_url"], dest)
    verify_sha256(dest, asset["sha256"])
    return [dest]


def vendor_snap(asset: dict[str, Any], out_dir: Path) -> list[Path]:
    snap = shutil.which("snap")
    if not snap:
        raise SystemExit("Linux Multipass vendoring requires the snap command")

    out_dir.mkdir(parents=True, exist_ok=True)
    before = set(out_dir.iterdir()) if out_dir.exists() else set()
    command = [snap, "download", asset["snap_name"]]
    if "snap_revision" in asset:
        command.extend(["--revision", str(asset["snap_revision"])])
    elif "snap_channel" in asset:
        command.extend(["--channel", asset["snap_channel"]])
    print("Running:", " ".join(command))
    subprocess.run(command, cwd=out_dir, check=True)

    created = [path for path in out_dir.iterdir() if path not in before]
    snap_files = sorted(path for path in created if path.suffix == ".snap")
    assert_files = sorted(path for path in created if path.suffix == ".assert")
    if len(snap_files) != 1 or len(assert_files) != 1:
        raise SystemExit(
            f"Expected one .snap and one .assert from snap download, got {created}"
        )

    snap_dest = out_dir / asset["file_name"]
    assert_dest = out_dir / "multipass.assert"
    snap_files[0].replace(snap_dest)
    assert_files[0].replace(assert_dest)
    verify_sha256(snap_dest, asset["sha256"])
    return [snap_dest, assert_dest]


def write_metadata(
    manifest: dict[str, Any], asset: dict[str, Any], out_dir: Path
) -> Path:
    metadata = {
        "preferred_version": selected_version(manifest, asset),
        "min_version": manifest["min_version"],
        "allow_newer": manifest.get("allow_newer", True),
        "blocked_versions": manifest.get("blocked_versions", []),
        "asset": asset,
    }
    dest = out_dir / "multipass.asset.json"
    dest.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return dest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--platform", default=current_platform())
    parser.add_argument("--arch", default=current_arch())
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    target_platform = normalize_platform(args.platform)
    target_arch = normalize_arch(args.arch)
    manifest = load_manifest(args.manifest)
    asset = select_asset(manifest, target_platform, target_arch)

    print(
        f"Selected Multipass {selected_version(manifest, asset)} "
        f"for {target_platform}/{target_arch}: {asset['file_name']}"
    )
    if args.dry_run:
        return 0

    args.out_dir.mkdir(parents=True, exist_ok=True)
    for path in args.out_dir.iterdir():
        if path.name.startswith("multipass"):
            if path.is_file():
                path.unlink()

    if target_platform == "linux":
        paths = vendor_snap(asset, args.out_dir)
    else:
        paths = vendor_direct(asset, args.out_dir)
    paths.append(write_metadata(manifest, asset, args.out_dir))

    for path in paths:
        print(f"Vendored {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
