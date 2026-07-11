#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from fractions import Fraction
from pathlib import Path


DEFAULT_DISCLAIMER = Path(__file__).resolve().parents[1] / "assets" / "disclaimer-zh-en-1920x1080.png"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepend a cover and disclaimer while stream-copying the source video body.")
    parser.add_argument("input", type=Path, help="Source MP4 video.")
    parser.add_argument("--cover-image", type=Path, required=True, help="Selected cover image.")
    parser.add_argument("--disclaimer-image", type=Path, default=DEFAULT_DISCLAIMER, help="Disclaimer image, defaults to the bundled asset.")
    parser.add_argument("--output", type=Path, required=True, help="Output MP4 path.")
    parser.add_argument("--cover-seconds", type=float, default=1.5, help="Cover duration, default 1.5 seconds.")
    parser.add_argument("--disclaimer-seconds", type=float, default=2.0, help="Disclaimer duration, default 2 seconds.")
    parser.add_argument("--preview-content-seconds", type=float, default=None, help="Copy only this many seconds of source content for a preview.")
    parser.add_argument("--overwrite", action="store_true", help="Replace an existing output file.")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without writing output.")
    return parser.parse_args()


def resolve_file(path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise RuntimeError(f"{label} was not found: {resolved}")
    return resolved


def require_tools() -> tuple[str, str]:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise RuntimeError("FFmpeg and ffprobe are required. Run python scripts/check_ffmpeg.py first.")
    return ffmpeg, ffprobe


def probe_media(ffprobe: str, source: Path) -> dict[str, object]:
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type,codec_name,profile,level,width,height,pix_fmt,r_frame_rate,time_base,sample_rate,channels,channel_layout,bit_rate",
            "-of",
            "json",
            str(source),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    streams = json.loads(result.stdout).get("streams", [])
    video = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    audio = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
    if not video:
        raise RuntimeError("Source video stream was not found.")
    if video.get("codec_name") != "h264" or video.get("pix_fmt") != "yuv420p":
        raise RuntimeError("Lightweight prepend currently requires H.264 yuv420p video. Use package_video.py for full re-encoding.")
    if audio and audio.get("codec_name") != "aac":
        raise RuntimeError("Lightweight prepend currently requires AAC audio. Use package_video.py for full re-encoding.")
    return {"video": video, "audio": audio}


def validate_args(args: argparse.Namespace) -> tuple[Path, Path, Path, Path]:
    source = resolve_file(args.input, "Source video")
    cover = resolve_file(args.cover_image, "Cover image")
    disclaimer = resolve_file(args.disclaimer_image, "Disclaimer image")
    output = args.output.expanduser().resolve()
    if source == output:
        raise RuntimeError("Output path must differ from the source video.")
    if output.suffix.lower() != ".mp4":
        raise RuntimeError("Output must use the .mp4 extension.")
    if output.exists() and not args.overwrite:
        raise RuntimeError("Output already exists. Confirm replacement, then add --overwrite.")
    if not 0.25 <= args.cover_seconds <= 10:
        raise RuntimeError("--cover-seconds must be between 0.25 and 10 seconds.")
    if not 0.5 <= args.disclaimer_seconds <= 10:
        raise RuntimeError("--disclaimer-seconds must be between 0.5 and 10 seconds.")
    if args.preview_content_seconds is not None and args.preview_content_seconds <= 0:
        raise RuntimeError("--preview-content-seconds must be greater than zero.")
    return source, cover, disclaimer, output


def concat_quote(path: Path) -> str:
    return str(path).replace("'", "'\\''")


def build_intro_command(
    ffmpeg: str,
    cover: Path,
    disclaimer: Path,
    intro: Path,
    media: dict[str, object],
    cover_seconds: float,
    disclaimer_seconds: float,
) -> list[str]:
    video = media["video"]
    audio = media["audio"]
    width = int(video["width"])
    height = int(video["height"])
    frame_rate = str(video["r_frame_rate"])
    fps = float(Fraction(frame_rate))
    sample_rate = int(audio.get("sample_rate", 48_000)) if audio else 48_000
    channels = int(audio.get("channels", 2)) if audio else 2
    channel_layout = str(audio.get("channel_layout") or ("mono" if channels == 1 else "stereo")) if audio else "stereo"
    audio_bitrate = int(audio.get("bit_rate") or 128_000) if audio else 128_000
    intro_seconds = cover_seconds + disclaimer_seconds
    gop = max(1, round(fps * 2))
    scale = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease:out_range=tv,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,format=yuv420p,"
        "setparams=range=tv:color_primaries=bt709:color_trc=bt709:colorspace=bt709"
    )
    command = [
        ffmpeg,
        "-hide_banner",
        "-y",
        "-loop",
        "1",
        "-framerate",
        frame_rate,
        "-t",
        f"{cover_seconds:g}",
        "-i",
        str(cover),
        "-loop",
        "1",
        "-framerate",
        frame_rate,
        "-t",
        f"{disclaimer_seconds:g}",
        "-i",
        str(disclaimer),
        "-f",
        "lavfi",
        "-t",
        f"{intro_seconds:g}",
        "-i",
        f"anullsrc=r={sample_rate}:cl={channel_layout}",
        "-filter_complex",
        f"[0:v]{scale},setpts=PTS-STARTPTS[v0];[1:v]{scale},setpts=PTS-STARTPTS[v1];[v0][v1]concat=n=2:v=1:a=0[v]",
        "-map",
        "[v]",
        "-map",
        "2:a:0",
        "-t",
        f"{intro_seconds:g}",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "18",
        "-profile:v",
        "high",
        "-level:v",
        f"{int(video.get('level') or 40) / 10:g}",
        "-pix_fmt",
        "yuv420p",
        "-color_range",
        "tv",
        "-colorspace",
        "bt709",
        "-color_primaries",
        "bt709",
        "-color_trc",
        "bt709",
        "-r",
        frame_rate,
        "-g",
        str(gop),
        "-keyint_min",
        str(gop),
        "-sc_threshold",
        "0",
        "-c:a",
        "aac",
        "-b:a",
        f"{audio_bitrate}",
        "-ar",
        str(sample_rate),
        "-ac",
        str(channels),
    ]
    time_base = str(video.get("time_base") or "1/90000")
    denominator = Fraction(time_base).denominator
    command.extend(["-video_track_timescale", str(denominator), "-movflags", "+faststart", str(intro)])
    return command


def build_concat_command(
    ffmpeg: str,
    concat_file: Path,
    output: Path,
    intro_seconds: float,
    preview_content_seconds: float | None,
    overwrite: bool,
) -> list[str]:
    command = [ffmpeg, "-hide_banner", "-y" if overwrite else "-n", "-f", "concat", "-safe", "0", "-i", str(concat_file)]
    if preview_content_seconds is not None:
        command.extend(["-t", f"{intro_seconds + preview_content_seconds:g}"])
    command.extend(["-map", "0:v:0", "-map", "0:a?", "-c", "copy", "-movflags", "+faststart", str(output)])
    return command


def main() -> int:
    args = parse_args()
    source, cover, disclaimer, output = validate_args(args)
    ffmpeg, ffprobe = require_tools()
    media = probe_media(ffprobe, source)
    output.parent.mkdir(parents=True, exist_ok=True)
    intro_seconds = args.cover_seconds + args.disclaimer_seconds
    with tempfile.TemporaryDirectory(prefix="video-publish-intro-") as temp_dir:
        temp_path = Path(temp_dir)
        intro = temp_path / "intro.mp4"
        concat_file = temp_path / "concat.txt"
        intro_command = build_intro_command(ffmpeg, cover, disclaimer, intro, media, args.cover_seconds, args.disclaimer_seconds)
        concat_file.write_text(f"file '{concat_quote(intro)}'\nfile '{concat_quote(source)}'\n", encoding="utf-8")
        concat_command = build_concat_command(ffmpeg, concat_file, output, intro_seconds, args.preview_content_seconds, args.overwrite)
        if args.dry_run:
            print(json.dumps({"intro_command": intro_command, "concat_command": concat_command}, ensure_ascii=False, indent=2))
            return 0
        subprocess.run(intro_command, check=True)
        subprocess.run(concat_command, check=True)
    print(
        json.dumps(
            {
                "output": str(output),
                "cover_image": str(cover),
                "disclaimer_image": str(disclaimer),
                "cover_seconds": args.cover_seconds,
                "disclaimer_seconds": args.disclaimer_seconds,
                "source_video_reencoded": False,
                "size_bytes": output.stat().st_size,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        print(f"video-publish: {error}", file=__import__("sys").stderr)
        raise SystemExit(2)
