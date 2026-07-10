#!/usr/bin/env bash
set -euo pipefail

MOUNT_POINT="${ALIST_MOUNT_POINT:-$HOME/AList-WebDAV}"

if mount | grep -Fq " on $MOUNT_POINT "; then
  umount "$MOUNT_POINT"
  echo "Unmounted: $MOUNT_POINT"
else
  echo "AList WebDAV is not mounted at: $MOUNT_POINT"
fi
