#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

mkdir -p \
  "$ROOT/runtime/alist" \
  "$ROOT/runtime/alist-data" \
  "$ROOT/runtime/aria2" \
  "$ROOT/runtime/downloads" \
  "$ROOT/runtime/logs"

SECRET_FILE="$ROOT/runtime/aria2/rpc-secret"
if [[ -n "${ARIA2_RPC_SECRET:-}" ]]; then
  SECRET="$ARIA2_RPC_SECRET"
elif [[ -f "$SECRET_FILE" ]]; then
  SECRET="$(cat "$SECRET_FILE")"
else
  SECRET="$(openssl rand -hex 16 2>/dev/null || date +%s | shasum | awk '{print substr($1,1,32)}')"
fi

printf "%s\n" "$SECRET" > "$SECRET_FILE"
chmod 600 "$SECRET_FILE"

cat > "$ROOT/runtime/aria2/aria2.conf" <<EOF
dir=$ROOT/runtime/downloads
daemon=false
continue=true
max-concurrent-downloads=3
max-connection-per-server=8
split=8
min-split-size=4M
auto-file-renaming=true
allow-overwrite=false

enable-rpc=true
rpc-listen-all=false
rpc-listen-port=6800
rpc-secret=$SECRET

save-session=$ROOT/runtime/aria2/aria2.session
save-session-interval=60

log=$ROOT/runtime/logs/aria2.log
log-level=notice
EOF

touch "$ROOT/runtime/aria2/aria2.session"
echo "Runtime initialized at: $ROOT/runtime"
