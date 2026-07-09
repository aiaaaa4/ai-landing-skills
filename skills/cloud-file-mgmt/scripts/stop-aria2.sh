#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$ROOT/runtime/aria2/aria2.pid"

if [[ ! -f "$PID_FILE" ]]; then
  echo "aria2 is not running"
  exit 0
fi

PID="$(cat "$PID_FILE")"
if kill -0 "$PID" 2>/dev/null; then
  kill "$PID"
  echo "aria2 stopped: $PID"
else
  echo "aria2 pid file was stale: $PID"
fi
rm -f "$PID_FILE"
