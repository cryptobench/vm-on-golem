#!/usr/bin/env bash
set -euo pipefail

repo="${GOLEM_CENTRAL_DISCOVERY_REPO:-cryptobench/vm-on-golem}"
install_path="${1:-${GOLEM_CENTRAL_DISCOVERY_BIN:-/usr/local/bin/golem-central-discovery}}"
api_base="${GITHUB_API_URL:-https://api.github.com}"

case "$(uname -s)" in
  Linux) os="linux" ;;
  Darwin) os="darwin" ;;
  *) echo "Unsupported OS: $(uname -s)" >&2; exit 1 ;;
esac

case "$(uname -m)" in
  x86_64|amd64) arch="amd64" ;;
  arm64|aarch64) arch="arm64" ;;
  *) echo "Unsupported architecture: $(uname -m)" >&2; exit 1 ;;
esac

asset="golem-central-discovery-${os}-${arch}.tar.gz"
tmpdir="$(mktemp -d)"
tmp_install=""
cleanup() {
  rm -rf "$tmpdir"
  if [ -n "$tmp_install" ] && [ -e "$tmp_install" ]; then
    rm -f "$tmp_install" 2>/dev/null || true
  fi
}
trap cleanup EXIT

curl_headers=(-H "Accept: application/vnd.github+json")
if [ -n "${GH_TOKEN:-${GITHUB_TOKEN:-}}" ]; then
  curl_headers+=(-H "Authorization: Bearer ${GH_TOKEN:-${GITHUB_TOKEN:-}}")
fi

release_json="$tmpdir/release.json"
curl -fsSL "${curl_headers[@]}" "$api_base/repos/$repo/releases/latest" -o "$release_json"

tag="$(sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p' "$release_json" | head -n 1)"
asset_url="$(grep -F "\"browser_download_url\"" "$release_json" | grep -F "/$asset\"" | sed -n 's/.*"browser_download_url": *"\([^"]*\)".*/\1/p' | head -n 1)"
checksums_url="$(grep -F "\"browser_download_url\"" "$release_json" | grep -F "/checksums.txt\"" | sed -n 's/.*"browser_download_url": *"\([^"]*\)".*/\1/p' | head -n 1)"

if [ -z "$tag" ]; then
  echo "Could not determine latest release tag for $repo" >&2
  exit 1
fi
if [ -z "$asset_url" ]; then
  echo "Release $tag does not contain $asset" >&2
  exit 1
fi
if [ -z "$checksums_url" ]; then
  echo "Release $tag does not contain checksums.txt" >&2
  exit 1
fi

archive="$tmpdir/$asset"
checksums="$tmpdir/checksums.txt"
curl -fsSL "${curl_headers[@]}" "$asset_url" -o "$archive"
curl -fsSL "${curl_headers[@]}" "$checksums_url" -o "$checksums"

expected="$(awk -v asset="$asset" '$2 == asset { print $1 }' "$checksums" | head -n 1)"
if [ -z "$expected" ]; then
  echo "checksums.txt does not include $asset" >&2
  exit 1
fi

if command -v sha256sum >/dev/null 2>&1; then
  actual="$(sha256sum "$archive" | awk '{print $1}')"
else
  actual="$(shasum -a 256 "$archive" | awk '{print $1}')"
fi
if [ "$actual" != "$expected" ]; then
  echo "Checksum mismatch for $asset" >&2
  echo "expected: $expected" >&2
  echo "actual:   $actual" >&2
  exit 1
fi

tar -xzf "$archive" -C "$tmpdir"
binary="$(find "$tmpdir" -type f -name golem-central-discovery -perm -u+x | head -n 1)"
if [ -z "$binary" ]; then
  echo "Archive did not contain an executable golem-central-discovery binary" >&2
  exit 1
fi

install_dir="$(dirname "$install_path")"
install_name="$(basename "$install_path")"
if [ ! -d "$install_dir" ]; then
  if ! mkdir -p "$install_dir" 2>/dev/null; then
    if ! command -v sudo >/dev/null 2>&1; then
      echo "Could not create $install_dir and sudo is not available" >&2
      exit 1
    fi
    sudo mkdir -p "$install_dir"
  fi
fi
tmp_install="$install_dir/.${install_name}.tmp.$$"

if [ -w "$install_dir" ]; then
  install -m 0755 "$binary" "$tmp_install"
  mv -f "$tmp_install" "$install_path"
else
  if ! command -v sudo >/dev/null 2>&1; then
    echo "$install_dir is not writable and sudo is not available" >&2
    exit 1
  fi
  sudo install -m 0755 "$binary" "$tmp_install"
  sudo mv -f "$tmp_install" "$install_path"
fi

echo "Installed golem-central-discovery $tag to $install_path"
