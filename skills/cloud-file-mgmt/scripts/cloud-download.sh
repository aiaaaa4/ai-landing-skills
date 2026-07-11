#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 <alist-mount-name> <remote-name-or-path> [local-file-or-directory]" >&2
}

if [[ $# -lt 2 || $# -gt 3 ]]; then
  usage
  exit 2
fi

MOUNT_NAME="$1"
REMOTE_NAME="$2"
LOCAL_TARGET="${3:-$PWD}"
BASE_URL="http://127.0.0.1:5244/dav"

case "$MOUNT_NAME" in
  ""|.|..|*/*)
    echo "AList mount name must be one non-empty top-level mount name without '/'." >&2
    exit 2
    ;;
  *)
    ;;
esac

if [[ -d "$LOCAL_TARGET" ]]; then
  LOCAL_TARGET="$LOCAL_TARGET/$(basename "$REMOTE_NAME")"
fi

if [[ -e "$LOCAL_TARGET" ]]; then
  echo "Local destination already exists: $LOCAL_TARGET" >&2
  exit 1
fi

if [[ -z "${ALIST_PASSWORD:-}" ]]; then
  read -rsp "AList password for admin: " ALIST_PASSWORD
  echo
fi

URL_PATH="$(python3 - "$MOUNT_NAME" "$REMOTE_NAME" <<'PY'
import sys
from urllib.parse import quote

mount_name, remote = sys.argv[1], sys.argv[2].strip("/")
parts = [quote(part) for part in remote.split("/") if part]
print("/".join([quote(mount_name)] + parts))
PY
)"

PARENT_DIR="$(dirname "$LOCAL_TARGET")"
mkdir -p "$PARENT_DIR"
TEMP_FILE="$(mktemp "$PARENT_DIR/.alist-download-XXXXXX")"
trap 'rm -f "$TEMP_FILE"' EXIT

echo "Downloading /$MOUNT_NAME/$REMOTE_NAME -> $LOCAL_TARGET"
curl --fail-with-body --location --silent --show-error \
  --user "admin:${ALIST_PASSWORD}" \
  --output "$TEMP_FILE" \
  "$BASE_URL/$URL_PATH"

mv "$TEMP_FILE" "$LOCAL_TARGET"
trap - EXIT
echo "Downloaded: $LOCAL_TARGET"
