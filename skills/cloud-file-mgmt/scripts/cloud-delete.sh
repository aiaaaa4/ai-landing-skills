#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 <alist-mount-name> <remote-name-or-path>" >&2
}

if [[ $# -ne 2 ]]; then
  usage
  exit 2
fi

MOUNT_NAME="$1"
REMOTE_NAME="$2"
BASE_URL="http://127.0.0.1:5244/dav"

case "$MOUNT_NAME" in
  ""|.|..|*/*)
    echo "AList mount name must be one non-empty top-level mount name without '/'." >&2
    exit 2
    ;;
  *)
    ;;
esac

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

echo "Deleting: /$MOUNT_NAME/$REMOTE_NAME"
curl --fail-with-body --silent --show-error \
  --user "admin:${ALIST_PASSWORD}" \
  --request DELETE \
  "$URL" >/dev/null
echo "Deleted: /$MOUNT_NAME/$REMOTE_NAME"
