#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MOUNT_POINT="$ROOT/AList-WebDAV"
WEBDAV_URL="http://127.0.0.1:5244/dav/"

mkdir -p "$MOUNT_POINT"

if mount | grep -q " on $MOUNT_POINT "; then
  echo "AList WebDAV is already mounted at: $MOUNT_POINT"
else
  echo "Mounting AList WebDAV at: $MOUNT_POINT"
  echo "Username: admin"
  echo "Enter the AList admin password when prompted."
  mount_webdav -i -v AList "$WEBDAV_URL" "$MOUNT_POINT"
fi

open "$MOUNT_POINT"
