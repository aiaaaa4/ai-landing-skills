#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
import shutil
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract randomized cover candidates from the first part of a video.")
    parser.add_argument("input", type=Path, help="Source video path.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory for cover PNG files and the contact sheet.")
    parser.add_argument("--count", type=int, default=5, help="Number of cover candidates, default 5.")
    parser.add_argument("--portion", type=float, default=0.5, help="Fraction of the video to sample, default first half.")
    parser.add_argument("--seed", type=int, default=None, help="Optional random seed for reproducible sampling.")
    parser.add_argument("--overwrite", action="store_true", help="Replace existing candidate files.")
    return parser.parse_args()


def require_tools() -> tuple[str, str]:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise RuntimeError("FFmpeg and ffprobe are required. Run python scripts/check_ffmpeg.py first.")
    return ffmpeg, ffprobe


def probe_duration(ffprobe: str, source: Path) -> float:
    result = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(source)],
        check=False,
        capture_output=True,
        text=True,
    )
    try:
        duration = float(result.stdout.strip())
    except ValueError as error:
        raise RuntimeError("Could not read the source video duration.") from error
    if duration <= 0:
        raise RuntimeError("Source video duration must be greater than zero.")
    return duration


def candidate_timestamps(
    duration: float,
    count: int,
    portion: float,
    rng: random.Random | None = None,
) -> list[float]:
    if not 1 <= count <= 12:
        raise RuntimeError("--count must be between 1 and 12.")
    if not 0.05 <= portion <= 1:
        raise RuntimeError("--portion must be between 0.05 and 1.0.")
    sampled_duration = duration * portion
    generator = rng or random.SystemRandom()
    segment = sampled_duration / count
    return [generator.uniform(index * segment + segment * 0.1, (index + 1) * segment - segment * 0.1) for index in range(count)]


def main() -> int:
    args = parse_args()
    source = args.input.expanduser().resolve()
    if not source.is_file():
        raise RuntimeError(f"Source video was not found: {source}")
    ffmpeg, ffprobe = require_tools()
    duration = probe_duration(ffprobe, source)
    rng = random.Random(args.seed) if args.seed is not None else None
    timestamps = candidate_timestamps(duration, args.count, args.portion, rng)
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    candidates: list[dict[str, object]] = []
    for index, timestamp in enumerate(timestamps, start=1):
        output = output_dir / f"抽帧封面{index}.png"
        subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-y" if args.overwrite else "-n",
                "-ss",
                f"{timestamp:.3f}",
                "-i",
                str(source),
                "-map",
                "0:v:0",
                "-frames:v",
                "1",
                "-update",
                "1",
                "-an",
                str(output),
            ],
            check=True,
        )
        candidates.append({"index": index, "timestamp_seconds": round(timestamp, 3), "path": str(output)})
    print(json.dumps({"source": str(source), "candidates": candidates}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        print(f"video-publish: {error}", file=sys.stderr)
        raise SystemExit(2)
