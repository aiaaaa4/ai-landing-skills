#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 <alist-mount-name> <local-file-or-folder> [remote-name-or-path]" >&2
}

if [[ $# -lt 2 || $# -gt 3 ]]; then
  usage
  exit 2
fi

MOUNT_NAME="$1"
SOURCE="$2"
REMOTE_NAME="${3:-}"
BASE_URL="http://127.0.0.1:5244/dav"

case "$MOUNT_NAME" in
  ""|.|..|*/*)
    echo "AList mount name must be one non-empty top-level mount name without '/'." >&2
    exit 2
    ;;
  *)
    ;;
esac

if [[ ! -e "$SOURCE" ]]; then
  echo "Local path not found: $SOURCE" >&2
  exit 1
fi

UPLOAD_PATH="$SOURCE"
CLEANUP_PATH=""

if [[ -d "$SOURCE" ]]; then
  NAME="$(basename "$SOURCE")"
  CLEANUP_PATH="$(mktemp -t alist-upload-XXXXXX).zip"
  echo "Packing folder/package before upload: $NAME -> $(basename "$CLEANUP_PATH")"
  ditto -c -k --sequesterRsrc --keepParent "$SOURCE" "$CLEANUP_PATH"
  UPLOAD_PATH="$CLEANUP_PATH"
  if [[ -z "$REMOTE_NAME" ]]; then
    REMOTE_NAME="$NAME.zip"
  fi
fi

if [[ -z "$REMOTE_NAME" ]]; then
  REMOTE_NAME="$(basename "$UPLOAD_PATH")"
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

URL="$BASE_URL/$URL_PATH"
SIZE="$(wc -c < "$UPLOAD_PATH" | tr -d ' ')"

echo "Uploading $UPLOAD_PATH ($SIZE bytes) -> /$MOUNT_NAME/$REMOTE_NAME"
curl --fail-with-body --silent --show-error \
  --user "admin:${ALIST_PASSWORD}" \
  --upload-file "$UPLOAD_PATH" \
  "$URL" >/dev/null
echo "Uploaded: /$MOUNT_NAME/$REMOTE_NAME"

if [[ -n "$CLEANUP_PATH" ]]; then
  rm -f "$CLEANUP_PATH"
fi
