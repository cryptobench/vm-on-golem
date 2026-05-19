#!/bin/sh
set -eu

MULTIPASS_DIR="/usr/lib/golem-provider/multipass"
SNAP_FILE="$MULTIPASS_DIR/multipass_1.16.2_amd64.snap"
ASSERT_FILE="$MULTIPASS_DIR/multipass.assert"
LOG_DIR="/var/log/golem-provider"
LOG_FILE="$LOG_DIR/installer-postinstall.log"
MIN_VERSION="1.13.0"
COMMAND_TIMEOUT_SECONDS=5
INSTALL_TIMEOUT_SECONDS=300
MULTIPASSD_SERVICE="snap.multipass.multipassd.service"
MULTIPASSD_FALLBACK_SERVICE="multipassd.service"

if ! mkdir -p "$LOG_DIR" 2>/dev/null; then
  LOG_FILE="${TMPDIR:-/tmp}/golem-provider-installer-postinstall.log"
fi

log() {
  timestamp="$(date -u '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || date)"
  printf "%s %s\n" "$timestamp" "$*" >&2
  { printf "%s %s\n" "$timestamp" "$*" >>"$LOG_FILE"; } 2>/dev/null || true
}

on_exit() {
  status="$?"
  if [ "$status" -eq 0 ]; then
    log "Golem Provider Linux postinstall completed successfully"
  else
    log "Golem Provider Linux postinstall failed with status $status"
  fi
}

trap on_exit EXIT

temp_file() {
  mktemp "${TMPDIR:-/tmp}/golem-provider-installer.XXXXXX"
}

log_file_contents() {
  output_file="$1"
  if [ -s "$output_file" ]; then
    while IFS= read -r output_line; do
      log "  $output_line"
    done <"$output_file"
  fi
}

run_capture_to_file() {
  timeout_seconds="$1"
  output_file="$2"
  log_output="$3"
  shift 3

  : >"$output_file"
  log "Running command with ${timeout_seconds}s timeout: $*"
  "$@" >"$output_file" 2>&1 &
  command_pid="$!"
  elapsed_seconds=0

  while kill -0 "$command_pid" 2>/dev/null; do
    if [ "$elapsed_seconds" -ge "$timeout_seconds" ]; then
      log "Command timed out after ${timeout_seconds}s: $*"
      kill "$command_pid" 2>/dev/null || true
      sleep 1
      kill -9 "$command_pid" 2>/dev/null || true
      wait "$command_pid" 2>/dev/null || true
      if [ "$log_output" = "1" ]; then
        log_file_contents "$output_file"
      fi
      return 124
    fi
    sleep 1
    elapsed_seconds=$((elapsed_seconds + 1))
  done

  if wait "$command_pid"; then
    command_status=0
  else
    command_status="$?"
  fi
  log "Command exited ${command_status}: $*"
  if [ "$log_output" = "1" ]; then
    log_file_contents "$output_file"
  fi
  return "$command_status"
}

run_logged() {
  timeout_seconds="$1"
  shift
  output_file="$(temp_file)"
  run_capture_to_file "$timeout_seconds" "$output_file" 1 "$@"
  command_status="$?"
  rm -f "$output_file"
  return "$command_status"
}

run_status_only() {
  timeout_seconds="$1"
  shift
  output_file="$(temp_file)"
  run_capture_to_file "$timeout_seconds" "$output_file" 0 "$@"
  command_status="$?"
  rm -f "$output_file"
  return "$command_status"
}

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
    log "Found Multipass on PATH: $(command -v multipass)"
    command -v multipass
  elif [ -x /snap/bin/multipass ]; then
    log "Found Multipass binary: /snap/bin/multipass"
    printf "/snap/bin/multipass"
  else
    log "No Multipass binary found"
    return 1
  fi
}

read_multipass_version() {
  mp="$1"
  output_file="$(temp_file)"
  if ! run_capture_to_file "$COMMAND_TIMEOUT_SECONDS" "$output_file" 1 "$mp" version; then
    rm -f "$output_file"
    return 1
  fi
  version="$(sed -n 's/.*multipass[[:space:]][[:space:]]*\([0-9][^[:space:]]*\).*/\1/p' "$output_file" | head -n 1)"
  rm -f "$output_file"
  if [ -z "$version" ]; then
    log "Unable to parse Multipass version"
    return 1
  fi
  log "Parsed Multipass version: $version"
  printf "%s" "$version"
}

multipass_supported() {
  mp="$(multipass_path)" || return 1
  version="$(read_multipass_version "$mp")"
  [ -n "$version" ] || return 1
  if version_lt "$version" "$MIN_VERSION"; then
    log "Multipass version $version is older than required $MIN_VERSION"
    return 1
  fi
  return 0
}

verify_multipass() {
  verify_multipass_service || return 1
  multipass_supported
}

verify_multipass_service() {
  if command -v snap >/dev/null 2>&1; then
    snap_installed=1
    run_status_only "$COMMAND_TIMEOUT_SECONDS" snap list multipass || snap_installed=0
  else
    snap_installed=0
  fi

  if command -v systemctl >/dev/null 2>&1; then
    for service_name in "$MULTIPASSD_SERVICE" "$MULTIPASSD_FALLBACK_SERVICE"; do
      if run_status_only "$COMMAND_TIMEOUT_SECONDS" systemctl cat "$service_name"; then
        if run_status_only "$COMMAND_TIMEOUT_SECONDS" systemctl is-active --quiet "$service_name"; then
          log "Multipass daemon service is active: $service_name"
          return 0
        fi

        log "Multipass daemon service is not active; attempting service start: $service_name"
        run_logged "$COMMAND_TIMEOUT_SECONDS" systemctl start "$service_name" || true
        if run_status_only "$COMMAND_TIMEOUT_SECONDS" systemctl is-active --quiet "$service_name"; then
          log "Multipass daemon service is active: $service_name"
          return 0
        fi
      fi
    done

    log "Multipass daemon service is not active"
    return 1
  fi

  if [ "$snap_installed" -eq 1 ]; then
    if snap services multipass 2>/dev/null | awk '$1 == "multipass.multipassd" && $3 == "active" { found = 1 } END { exit found ? 0 : 1 }'; then
      log "Multipass daemon snap service is active"
      return 0
    fi

    log "Multipass daemon snap service is not active; attempting snap start"
    run_logged "$COMMAND_TIMEOUT_SECONDS" snap start multipass || true
    if snap services multipass 2>/dev/null | awk '$1 == "multipass.multipassd" && $3 == "active" { found = 1 } END { exit found ? 0 : 1 }'; then
      log "Multipass daemon snap service is active"
      return 0
    fi
  fi

  log "Unable to verify Multipass daemon service"
  return 1
}

log_diagnostics() {
  log "Diagnostics begin"
  log "User: $(id 2>/dev/null || true)"
  log "PATH: ${PATH:-}"
  log "TMPDIR: ${TMPDIR:-}"
  log "Log file: $LOG_FILE"
  if command -v snap >/dev/null 2>&1; then
    run_logged "$COMMAND_TIMEOUT_SECONDS" snap list multipass || true
    run_logged "$COMMAND_TIMEOUT_SECONDS" snap services multipass || true
  else
    log "snap command not found"
  fi
  if command -v systemctl >/dev/null 2>&1; then
    run_logged "$COMMAND_TIMEOUT_SECONDS" systemctl status snap.multipass.multipassd.service --no-pager || true
  else
    log "systemctl command not found"
  fi
  log "Diagnostics end"
}

log "Golem Provider Linux postinstall started"
log "Log file: $LOG_FILE"

log "Verifying existing Multipass installation"
if verify_multipass; then
  log "Multipass verification succeeded"
  log "Compatible Multipass already installed"
  exit 0
fi

if ! command -v snap >/dev/null 2>&1; then
  log "snapd is required to install Multipass on Linux"
  log_diagnostics
  exit 1
fi

if [ ! -f "$SNAP_FILE" ] || [ ! -f "$ASSERT_FILE" ]; then
  log "Bundled Multipass snap or assertion is missing from $MULTIPASS_DIR"
  log_diagnostics
  exit 1
fi

if ! run_logged "$INSTALL_TIMEOUT_SECONDS" snap ack "$ASSERT_FILE"; then
  log "Bundled Multipass assertion failed"
  log_diagnostics
  exit 1
fi

if run_logged "$COMMAND_TIMEOUT_SECONDS" snap list multipass; then
  if ! run_logged "$INSTALL_TIMEOUT_SECONDS" snap refresh "$SNAP_FILE"; then
    log "Bundled Multipass snap refresh failed"
    log_diagnostics
    exit 1
  fi
else
  if ! run_logged "$INSTALL_TIMEOUT_SECONDS" snap install "$SNAP_FILE"; then
    log "Bundled Multipass snap install failed"
    log_diagnostics
    exit 1
  fi
fi

log "Verifying installed Multipass package"
if ! verify_multipass; then
  log "Multipass installed but verification failed"
  log_diagnostics
  exit 1
fi

log "Multipass verification succeeded"
log "Multipass installed and verified"
