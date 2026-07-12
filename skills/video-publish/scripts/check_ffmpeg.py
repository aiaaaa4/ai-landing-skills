#!/usr/bin/env python3
from __future__ import annotations

import shutil
import sys

def main() -> int:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if ffmpeg and ffprobe:
        print(f"FFmpeg ready: {ffmpeg}")
        print(f"ffprobe ready: {ffprobe}")
        return 0
    missing = [name for name, value in (("ffmpeg", ffmpeg), ("ffprobe", ffprobe)) if not value]
    print(
        f"Missing required executable(s): {', '.join(missing)}. "
        "Install FFmpeg manually from ffmpeg.org or a trusted package manager, then rerun this check.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
