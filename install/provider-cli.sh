#!/bin/sh
set -eu

REPO="${GOLEM_PROVIDER_INSTALLER_REPO:-cryptobench/vm-on-golem}"
VERSION="latest"
INSTALL_DIR="${GOLEM_PROVIDER_INSTALLER_INSTALL_DIR:-}"
START_AFTER_INSTALL=0
SKIP_MULTIPASS=0
DRY_RUN=0

LINUX_MULTIPASS_SNAP_NAME="multipass"
LINUX_MULTIPASS_SNAP_REVISION="17096"
LINUX_MULTIPASS_SNAP_FILE="multipass_1.16.2_amd64.snap"
LINUX_MULTIPASS_SHA256="41ca8a4a8445a5bd1a74a5e34ad34354928c5d75c71cfc6739ebef16a38f3c0b"
MACOS_MULTIPASS_URL="https://github.com/canonical/multipass/releases/download/v1.16.1/multipass-1.16.1%2Bmac-Darwin.pkg"
MACOS_MULTIPASS_FILE="multipass-1.16.1+mac-Darwin.pkg"
MACOS_MULTIPASS_SHA256="758d10dc1b71872b0ee7a17070b93fc788dba5ba45c36b980e42fd895d273489"
MIN_MULTIPASS_VERSION="1.13.0"

usage() {
  cat <<EOF
Usage: provider-cli.sh [--start] [--version <tag>] [--install-dir <path>] [--no-multipass] [--dry-run]

Installs the Golem Provider CLI from GitHub Releases.
EOF
}

log() {
  printf '%s\n' "$*"
}

fail() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --start)
      START_AFTER_INSTALL=1
      shift
      ;;
    --version)
      [ "$#" -ge 2 ] || fail "--version requires a tag"
      VERSION="$2"
      shift 2
      ;;
    --install-dir)
      [ "$#" -ge 2 ] || fail "--install-dir requires a path"
      INSTALL_DIR="$2"
      shift 2
      ;;
    --no-multipass)
      SKIP_MULTIPASS=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      fail "Unknown option: $1"
      ;;
  esac
done

need_command() {
  command -v "$1" >/dev/null 2>&1 || fail "$1 is required"
}

download() {
  url="$1"
  dest="$2"
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$url" -o "$dest"
  elif command -v wget >/dev/null 2>&1; then
    wget -q "$url" -O "$dest"
  else
    fail "curl or wget is required"
  fi
}

download_stdout() {
  url="$1"
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$url"
  elif command -v wget >/dev/null 2>&1; then
    wget -q "$url" -O -
  else
    fail "curl or wget is required"
  fi
}

sha256_file() {
  path="$1"
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$path" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$path" | awk '{print $1}'
  else
    fail "sha256sum or shasum is required"
  fi
}

verify_sha256() {
  path="$1"
  expected="$2"
  actual="$(sha256_file "$path")"
  [ "$actual" = "$expected" ] || fail "SHA256 mismatch for $path: expected $expected, got $actual"
}

detect_target() {
  os="${GOLEM_PROVIDER_INSTALLER_OS:-$(uname -s 2>/dev/null || true)}"
  arch="${GOLEM_PROVIDER_INSTALLER_ARCH:-$(uname -m 2>/dev/null || true)}"

  case "$os" in
    Linux) platform="linux" ;;
    Darwin) platform="macos" ;;
    *) fail "Unsupported OS for provider CLI installer: $os" ;;
  esac

  case "$arch" in
    x86_64|amd64) normalized_arch="x86_64" ;;
    arm64|aarch64) normalized_arch="arm64" ;;
    *) fail "Unsupported CPU architecture for provider CLI installer: $arch" ;;
  esac

  target="${platform}-${normalized_arch}"
  case "$target" in
    linux-x86_64|macos-arm64) printf '%s' "$target" ;;
    *) fail "No provider CLI binary is published for $target yet" ;;
  esac
}

resolve_tag() {
  if [ "$VERSION" != "latest" ]; then
    printf '%s' "$VERSION"
    return
  fi
  api_url="https://api.github.com/repos/${REPO}/releases/latest"
  tag="$(download_stdout "$api_url" | sed -n 's/.*"tag_name"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n 1)"
  [ -n "$tag" ] || fail "Could not resolve latest GitHub release for $REPO"
  printf '%s' "$tag"
}

default_install_dir() {
  if [ -n "$INSTALL_DIR" ]; then
    printf '%s' "$INSTALL_DIR"
  elif [ -d /usr/local/bin ]; then
    printf '%s' /usr/local/bin
  else
    printf '%s' "$HOME/.local/bin"
  fi
}

copy_executable() {
  source="$1"
  dest="$2"
  dest_dir="$(dirname "$dest")"
  if mkdir -p "$dest_dir" 2>/dev/null && [ -w "$dest_dir" ]; then
    cp "$source" "$dest"
    chmod 755 "$dest"
  elif command -v sudo >/dev/null 2>&1; then
    sudo mkdir -p "$dest_dir"
    sudo cp "$source" "$dest"
    sudo chmod 755 "$dest"
  else
    fail "$dest_dir is not writable and sudo was not found"
  fi
}

version_core() {
  printf '%s' "$1" | sed 's/[+-].*$//'
}

version_lt() {
  awk -v a="$(version_core "$1")" -v b="$(version_core "$2")" 'BEGIN {
    split(a, av, "."); split(b, bv, ".");
    for (i = 1; i <= 3; i++) {
      ai = av[i] + 0; bi = bv[i] + 0;
      if (ai < bi) exit 0;
      if (ai > bi) exit 1;
    }
    exit 1;
  }'
}

multipass_path() {
  for candidate in \
    "/Library/Application Support/com.canonical.multipass/bin/multipass" \
    /snap/bin/multipass \
    /opt/homebrew/bin/multipass \
    /usr/local/bin/multipass \
    /usr/bin/multipass
  do
    if [ -x "$candidate" ]; then
      printf '%s' "$candidate"
      return 0
    fi
  done
  command -v multipass 2>/dev/null || return 1
}

multipass_version() {
  "$1" version 2>/dev/null | sed -n 's/.*multipass[[:space:]][[:space:]]*\([0-9][^[:space:]]*\).*/\1/p' | head -n 1
}

multipass_supported() {
  mp="$(multipass_path)" || return 1
  version="$(multipass_version "$mp")"
  [ -n "$version" ] || return 1
  if version_lt "$version" "$MIN_MULTIPASS_VERSION"; then
    return 1
  fi
  if [ "$(uname -s)" = "Darwin" ] && [ "$(uname -m)" = "arm64" ] && [ "$version" = "1.16.2+mac" ]; then
    return 1
  fi
  "$mp" version >/dev/null 2>&1
}

run_root() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
  elif command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  else
    fail "This step requires root privileges and sudo was not found: $*"
  fi
}

install_linux_multipass() {
  need_command snap
  work_dir="$1"
  log "Installing pinned Multipass snap..."
  (
    cd "$work_dir"
    snap download "$LINUX_MULTIPASS_SNAP_NAME" --revision "$LINUX_MULTIPASS_SNAP_REVISION" >/dev/null
  )
  snap_file="$(find "$work_dir" -maxdepth 1 -name '*.snap' -print | head -n 1)"
  assert_file="$(find "$work_dir" -maxdepth 1 -name '*.assert' -print | head -n 1)"
  [ -n "$snap_file" ] && [ -n "$assert_file" ] || fail "snap download did not produce Multipass snap and assertion files"
  verify_sha256 "$snap_file" "$LINUX_MULTIPASS_SHA256"
  run_root snap ack "$assert_file"
  if snap list multipass >/dev/null 2>&1; then
    run_root snap refresh "$snap_file"
  else
    run_root snap install "$snap_file"
  fi
}

install_macos_multipass() {
  work_dir="$1"
  pkg="$work_dir/$MACOS_MULTIPASS_FILE"
  log "Installing pinned Multipass package..."
  download "$MACOS_MULTIPASS_URL" "$pkg"
  verify_sha256 "$pkg" "$MACOS_MULTIPASS_SHA256"
  run_root /usr/sbin/installer -pkg "$pkg" -target /
}

install_or_verify_multipass() {
  if [ "$SKIP_MULTIPASS" -ne 0 ]; then
    return 0
  fi
  if multipass_supported; then
    log "Multipass is already installed and compatible."
    return
  fi
  case "$(uname -s)" in
    Linux) install_linux_multipass "$1" ;;
    Darwin) install_macos_multipass "$1" ;;
    *) fail "Unsupported OS for Multipass installation" ;;
  esac
  multipass_supported || fail "Multipass installed but did not pass verification"
}

target="$(detect_target)"
tag="$(resolve_tag)"
asset="golem-provider-cli-${target}"
install_dir="$(default_install_dir)"
install_path="${install_dir}/golem-provider"
download_base="${GOLEM_PROVIDER_INSTALLER_BASE_URL:-https://github.com/${REPO}/releases/download/${tag}}"

if [ "$DRY_RUN" -eq 1 ]; then
  log "target=$target"
  log "tag=$tag"
  log "asset=$asset"
  log "asset_url=${download_base}/${asset}"
  log "checksums_url=${download_base}/checksums.txt"
  log "install_path=$install_path"
  exit 0
fi

tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/golem-provider-cli.XXXXXX")"
trap 'rm -rf "$tmp_dir"' EXIT

log "Installing Golem Provider CLI ${tag} for ${target}..."
download "${download_base}/${asset}" "$tmp_dir/$asset"
download "${download_base}/checksums.txt" "$tmp_dir/checksums.txt"
expected_sha="$(awk -v asset="$asset" '$2 == asset {print $1}' "$tmp_dir/checksums.txt" | head -n 1)"
[ -n "$expected_sha" ] || fail "checksums.txt does not contain $asset"
verify_sha256 "$tmp_dir/$asset" "$expected_sha"
copy_executable "$tmp_dir/$asset" "$install_path"

install_or_verify_multipass "$tmp_dir"

log "Validating provider host requirements..."
"$install_path" requirements check

if [ "$START_AFTER_INSTALL" -eq 1 ]; then
  log "Starting Golem Provider..."
  exec "$install_path" start
fi

log ""
log "Golem Provider CLI installed: $install_path"
log "Start the provider with:"
log "  golem-provider start"

case ":$PATH:" in
  *":$install_dir:"*) ;;
  *) log "Note: add $install_dir to PATH if 'golem-provider' is not found." ;;
esac
