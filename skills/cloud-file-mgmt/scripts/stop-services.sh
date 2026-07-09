#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ALIST_BIN="${ALIST_BIN:-$ROOT/runtime/alist/alist}"
ALIST_DATA="${ALIST_DATA:-$ROOT/runtime/alist-data}"
ARIA2_BIN="${ARIA2_BIN:-/opt/homebrew/bin/aria2c}"
ARIA2_CONF="${ARIA2_CONF:-$ROOT/runtime/aria2/aria2.conf}"

stop_screen() {
  local name="$1"
  if screen -ls | grep -q "[.]$name[[:space:]]"; then
    screen -S "$name" -X quit
    echo "$name stopped"
  else
    echo "$name is not running"
  fi
}

stop_screen "cloud_file_mgmt_alist"
stop_screen "cloud_file_mgmt_aria2"

pkill -f "$ALIST_BIN server --data $ALIST_DATA" 2>/dev/null || true
pkill -f "$ARIA2_BIN --conf-path=$ARIA2_CONF" 2>/dev/null || true
