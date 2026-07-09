#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SECRET_FILE="$ROOT/runtime/aria2/rpc-secret"
ARIA2_RPC_SECRET="${ARIA2_RPC_SECRET:-}"

if [[ -z "$ARIA2_RPC_SECRET" && -f "$SECRET_FILE" ]]; then
  ARIA2_RPC_SECRET="$(cat "$SECRET_FILE")"
fi

if curl --silent --fail --max-time 2 http://127.0.0.1:5244/ >/dev/null; then
  echo "AList: running at http://127.0.0.1:5244"
else
  echo "AList: stopped"
fi

if [[ -n "$ARIA2_RPC_SECRET" ]]; then
  ARIA2_PARAMS="\"token:$ARIA2_RPC_SECRET\""
else
  ARIA2_PARAMS=""
fi

if curl --silent --fail --max-time 2 \
  http://127.0.0.1:6800/jsonrpc \
  --header 'Content-Type: application/json' \
  --data "{\"jsonrpc\":\"2.0\",\"id\":\"status\",\"method\":\"aria2.getVersion\",\"params\":[$ARIA2_PARAMS]}" \
  >/dev/null; then
  echo "aria2: running at http://127.0.0.1:6800/jsonrpc"
else
  echo "aria2: stopped"
fi
