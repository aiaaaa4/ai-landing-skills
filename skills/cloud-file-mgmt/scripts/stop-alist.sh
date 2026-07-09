#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$ROOT/runtime/alist/alist.pid"
ALIST_BIN="${ALIST_BIN:-$ROOT/runtime/alist/alist}"
ALIST_DATA="${ALIST_DATA:-$ROOT/runtime/alist-data}"

if [[ ! -f "$PID_FILE" ]]; then
  echo "AList is not running"
  exit 0
fi

PID="$(cat "$PID_FILE")"
if kill -0 "$PID" 2>/dev/null; then
  "$ALIST_BIN" stop --data "$ALIST_DATA" >/dev/null 2>&1 || kill "$PID"
  echo "AList stopped: $PID"
else
  echo "AList pid file was stale: $PID"
fi
rm -f "$PID_FILE"
