#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$ROOT/runtime/aria2/aria2.pid"
CONF="${ARIA2_CONF:-$ROOT/runtime/aria2/aria2.conf}"
ARIA2_BIN="${ARIA2_BIN:-/opt/homebrew/bin/aria2c}"

if [[ ! -f "$CONF" ]]; then
  "$ROOT/scripts/init-runtime.sh"
fi

if [[ ! -x "$ARIA2_BIN" ]]; then
  echo "aria2 binary not executable: $ARIA2_BIN" >&2
  echo "Install aria2 or set ARIA2_BIN." >&2
  exit 1
fi

if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "aria2 is already running: $(cat "$PID_FILE")"
  exit 0
fi

touch "$ROOT/runtime/aria2/aria2.session"
"$ARIA2_BIN" --conf-path="$CONF" >/dev/null 2>&1
sleep 0.5
PID="$(pgrep -f "$ARIA2_BIN --conf-path=$CONF" | head -n 1 || true)"
if [[ -z "$PID" ]]; then
  echo "aria2 failed to start; check $ROOT/runtime/logs/aria2.log" >&2
  exit 1
fi
echo "$PID" > "$PID_FILE"
echo "aria2 started: $(cat "$PID_FILE")"
