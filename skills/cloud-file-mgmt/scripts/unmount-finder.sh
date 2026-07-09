#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MOUNT_POINT="$ROOT/AList-WebDAV"

if mount | grep -q " on $MOUNT_POINT "; then
  umount "$MOUNT_POINT"
  echo "Unmounted: $MOUNT_POINT"
else
  echo "AList WebDAV is not mounted at: $MOUNT_POINT"
fi
