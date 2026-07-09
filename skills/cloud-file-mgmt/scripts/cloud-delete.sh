#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 <baidu|quark> <remote-name-or-path>" >&2
}

if [[ $# -ne 2 ]]; then
  usage
  exit 2
fi

DRIVE="$1"
REMOTE_NAME="$2"
BASE_URL="http://127.0.0.1:5244/dav"

case "$DRIVE" in
  baidu|quark) ;;
  *)
    echo "Drive must be baidu or quark." >&2
    exit 2
    ;;
esac

if [[ -z "${ALIST_PASSWORD:-}" ]]; then
  read -rsp "AList password for admin: " ALIST_PASSWORD
  echo
fi

URL_PATH="$(python3 - "$DRIVE" "$REMOTE_NAME" <<'PY'
import sys
from urllib.parse import quote

drive, remote = sys.argv[1], sys.argv[2].strip("/")
parts = [quote(part) for part in remote.split("/") if part]
print("/".join([quote(drive)] + parts))
PY
)"

URL="$BASE_URL/$URL_PATH"

echo "Deleting: /$DRIVE/$REMOTE_NAME"
curl --fail-with-body --silent --show-error \
  --user "admin:${ALIST_PASSWORD}" \
  --request DELETE \
  "$URL" >/dev/null
echo "Deleted: /$DRIVE/$REMOTE_NAME"
