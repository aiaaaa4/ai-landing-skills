#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$ROOT/runtime/alist/alist.pid"
BIN="${ALIST_BIN:-$ROOT/runtime/alist/alist}"
DATA="${ALIST_DATA:-$ROOT/runtime/alist-data}"
LOG="$ROOT/runtime/logs/alist.log"

mkdir -p "$ROOT/runtime/alist" "$DATA" "$ROOT/runtime/logs"

if [[ ! -x "$BIN" ]]; then
  echo "AList binary not executable: $BIN" >&2
  echo "Put AList at runtime/alist/alist or set ALIST_BIN." >&2
  exit 1
fi

if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "AList is already running: $(cat "$PID_FILE")"
  exit 0
fi

"$BIN" start --data "$DATA" >"$LOG" 2>&1
sleep 0.5
PID="$(pgrep -f "$BIN server --force-bin-dir --data $DATA|$BIN server --data $DATA|$BIN" | head -n 1 || true)"
if [[ -z "$PID" ]]; then
  echo "AList failed to start; check $LOG" >&2
  exit 1
fi
echo "$PID" > "$PID_FILE"
echo "AList started: $(cat "$PID_FILE")"
