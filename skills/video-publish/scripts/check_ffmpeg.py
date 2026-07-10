#!/usr/bin/env python3
from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys


REQUIRED_FILTERS = {"drawtext", "subtitles"}

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check or explicitly install FFmpeg for video-publish.")
    parser.add_argument("--install", action="store_true", help="Install FFmpeg only when it is missing.")
    return parser.parse_args()


def ffmpeg_available() -> bool:
    return bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def supported_filters() -> set[str]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return set()
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-filters"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return {name for name in REQUIRED_FILTERS if name in result.stdout}


def ffmpeg_ready() -> bool:
    return ffmpeg_available() and REQUIRED_FILTERS.issubset(supported_filters())


def install_ffmpeg() -> None:
    system = platform.system()
    if system == "Darwin":
        brew = shutil.which("brew")
        if not brew:
            raise RuntimeError("Homebrew is required on macOS. Install Homebrew first, then rerun with --install.")
        subprocess.run([brew, "tap", "homebrew-ffmpeg/ffmpeg"], check=True)
        if ffmpeg_available():
            subprocess.run([brew, "uninstall", "ffmpeg"], check=True)
        subprocess.run([brew, "install", "homebrew-ffmpeg/ffmpeg/ffmpeg"], check=True)
        return
    if system == "Linux":
        raise RuntimeError("Install FFmpeg with your distribution package manager, then rerun this check.")
    if system == "Windows":
        raise RuntimeError("Install FFmpeg with winget or a trusted package manager, then rerun this check.")
    raise RuntimeError(f"Unsupported operating system: {system}")


def main() -> int:
    args = parse_args()
    if ffmpeg_ready():
        print("FFmpeg, ffprobe, drawtext, and subtitles are available.")
        return 0
    if not args.install:
        missing = ", ".join(sorted(REQUIRED_FILTERS - supported_filters())) or "ffmpeg/ffprobe"
        print(f"FFmpeg is missing required publish filters: {missing}. Re-run with --install after user approval.", file=sys.stderr)
        return 2
    install_ffmpeg()
    if not ffmpeg_ready():
        print("FFmpeg installation finished but required publish filters are still unavailable.", file=sys.stderr)
        return 3
    print("FFmpeg installation completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
