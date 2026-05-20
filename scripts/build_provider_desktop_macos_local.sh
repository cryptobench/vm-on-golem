#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOWNLOADS_DIR="${DOWNLOADS_DIR:-$HOME/Downloads}"

cd "$ROOT"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This local package script only supports macOS." >&2
  exit 1
fi

echo "Vendoring Multipass for macOS..."
python scripts/vendor_multipass.py --platform darwin --arch universal

echo "Building provider sidecar..."
poetry -C provider-server run python ../scripts/build_provider_cli.py --onefile

echo "Building provider desktop app..."
npm --workspace @golem/provider-desktop run tauri:build

echo "Wrapping app in macOS pkg..."
python scripts/package_provider_desktop_macos.py

version="$(node -p "require('./apps/provider-desktop/package.json').version")"
pkg="$ROOT/apps/provider-desktop/src-tauri/target/release/bundle/pkg/Golem Provider_${version}_universal.pkg"
downloads_pkg="$DOWNLOADS_DIR/Golem Provider_${version}_universal.pkg"
simple_downloads_pkg="$DOWNLOADS_DIR/golem-provider-${version}.pkg"

if [[ ! -f "$pkg" ]]; then
  echo "Expected package was not created: $pkg" >&2
  exit 1
fi

mkdir -p "$DOWNLOADS_DIR"
cp -f "$pkg" "$downloads_pkg"
cp -f "$pkg" "$simple_downloads_pkg"

echo "Copied packages:"
ls -lh "$downloads_pkg" "$simple_downloads_pkg"

echo "SHA256:"
shasum -a 256 "$downloads_pkg"

echo "Payload check:"
pkgutil --payload-files "$pkg" \
  | grep -E "multipass-1\\.16\\.1\\+mac-Darwin\\.pkg|Contents/MacOS/golem-provider$|Contents/MacOS/golem-provider-desktop$"

echo "Signature check:"
pkgutil --check-signature "$pkg" || true
