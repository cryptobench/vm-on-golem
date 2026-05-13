#!/bin/sh
set -eu

MULTIPASS_DIR="/usr/lib/golem-provider/multipass"
SNAP_FILE="$MULTIPASS_DIR/multipass_1.16.2_amd64.snap"
ASSERT_FILE="$MULTIPASS_DIR/multipass.assert"
MIN_VERSION="1.13.0"

version_core() {
  printf "%s" "$1" | sed 's/[+-].*$//'
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
  if command -v multipass >/dev/null 2>&1; then
    command -v multipass
  elif [ -x /snap/bin/multipass ]; then
    printf "/snap/bin/multipass"
  else
    return 1
  fi
}

multipass_version() {
  "$1" version 2>&1 | sed -n 's/.*multipass[[:space:]]\+\([0-9][^[:space:]]*\).*/\1/p' | head -n 1
}

verify_multipass() {
  mp="$(multipass_path)" || return 1
  version="$(multipass_version "$mp")"
  [ -n "$version" ] || return 1
  if version_lt "$version" "$MIN_VERSION"; then
    return 1
  fi
  "$mp" list --format json >/dev/null 2>&1
}

if verify_multipass; then
  echo "Compatible Multipass already installed"
  exit 0
fi

if ! command -v snap >/dev/null 2>&1; then
  echo "snapd is required to install Multipass on Linux" >&2
  exit 1
fi

if [ ! -f "$SNAP_FILE" ] || [ ! -f "$ASSERT_FILE" ]; then
  echo "Bundled Multipass snap or assertion is missing from $MULTIPASS_DIR" >&2
  exit 1
fi

snap ack "$ASSERT_FILE"
if snap list multipass >/dev/null 2>&1; then
  snap refresh "$SNAP_FILE"
else
  snap install "$SNAP_FILE"
fi

if ! verify_multipass; then
  echo "Multipass installed but verification failed" >&2
  exit 1
fi

echo "Multipass installed and verified"
