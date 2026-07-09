#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ALIST_BIN="${ALIST_BIN:-$ROOT/runtime/alist/alist}"
ALIST_DATA="${ALIST_DATA:-$ROOT/runtime/alist-data}"
ARIA2_BIN="${ARIA2_BIN:-/opt/homebrew/bin/aria2c}"
ARIA2_CONF="${ARIA2_CONF:-$ROOT/runtime/aria2/aria2.conf}"

if [[ ! -f "$ARIA2_CONF" ]]; then
  "$ROOT/scripts/init-runtime.sh"
fi

if [[ ! -x "$ARIA2_BIN" ]]; then
  echo "aria2 binary not executable: $ARIA2_BIN" >&2
  exit 1
fi

if [[ ! -x "$ALIST_BIN" ]]; then
  echo "AList binary not executable: $ALIST_BIN" >&2
  echo "Put AList at runtime/alist/alist or set ALIST_BIN." >&2
  exit 1
fi

start_screen() {
  local name="$1"
  shift
  if screen -ls | grep -q "[.]$name[[:space:]]"; then
    echo "$name is already running"
    return
  fi
  screen -dmS "$name" "$@"
  echo "$name started"
}

touch "$ROOT/runtime/aria2/aria2.session"

start_screen "cloud_file_mgmt_aria2" \
  "$ARIA2_BIN" \
  --conf-path="$ARIA2_CONF"

start_screen "cloud_file_mgmt_alist" \
  "$ALIST_BIN" \
  server \
  --data "$ALIST_DATA" \
  --log-std
