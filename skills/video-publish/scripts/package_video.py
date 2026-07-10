#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


SUBTITLE_SUFFIXES = {".ass", ".ssa", ".srt", ".vtt"}
WATERMARK_MODES = {"drift", "top-right", "top-left", "bottom-right", "bottom-left"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Package a local video with optional disclaimer, subtitle burn-in, and text watermark.")
    parser.add_argument("input", type=Path, help="Confirmed local source video.")
    parser.add_argument("--output", type=Path, required=True, help="Confirmed MP4 output path.")
    parser.add_argument("--subtitle", type=Path, default=None, help="Optional ASS/SRT/SSA/VTT subtitle file to burn into video.")
    parser.add_argument("--disclaimer-text", default="", help="Optional opening disclaimer text.")
    parser.add_argument("--disclaimer-seconds", type=float, default=3.0, help="Opening disclaimer duration, 2-3 seconds recommended.")
    parser.add_argument("--disclaimer-mode", choices=["full-screen", "overlay"], default="full-screen")
    parser.add_argument("--mute-disclaimer-audio", action="store_true", help="Mute original audio during the disclaimer interval.")
    parser.add_argument("--watermark-text", default="", help="Optional watermark text.")
    parser.add_argument("--watermark-mode", choices=sorted(WATERMARK_MODES), default="drift")
    parser.add_argument("--watermark-opacity", type=float, default=0.45)
    parser.add_argument("--font", type=Path, default=None, help="Optional font file for Chinese text rendering.")
    parser.add_argument("--trim-start", default=None, help="Optional start timestamp, for example 00:00:05.")
    parser.add_argument("--trim-duration", default=None, help="Optional duration timestamp, for example 00:01:20.")
    parser.add_argument("--encoder", choices=["auto", "h264_videotoolbox", "libx264"], default="auto")
    parser.add_argument("--quality", choices=["balanced", "high"], default="balanced")
    parser.add_argument("--overwrite", action="store_true", help="Allow replacing the confirmed existing output file.")
    parser.add_argument("--dry-run", action="store_true", help="Print the FFmpeg command without writing output.")
    return parser.parse_args()


def require_ffmpeg(required_filters: set[str]) -> tuple[str, str]:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise RuntimeError("FFmpeg and ffprobe are required. Run python scripts/check_ffmpeg.py first.")
    if required_filters:
        result = subprocess.run(
            [ffmpeg, "-hide_banner", "-filters"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        missing = sorted(name for name in required_filters if name not in result.stdout)
        if missing:
            raise RuntimeError(f"FFmpeg is missing required filters: {', '.join(missing)}. Run python scripts/check_ffmpeg.py --install.")
    return ffmpeg, ffprobe


def resolve_existing(path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise RuntimeError(f"{label} was not found: {resolved}")
    return resolved


def default_font() -> Path | None:
    mac_candidates = [
        Path("/System/Library/Fonts/Hiragino Sans GB.ttc"),
        Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
    ]
    if sys.platform == "darwin":
        try:
            result = subprocess.run(
                ["fc-match", "-f", "%{file}", "PingFang SC"],
                check=False,
                capture_output=True,
                text=True,
            )
            candidate = Path(result.stdout.strip())
            if candidate.is_file():
                return candidate
        except FileNotFoundError:
            pass
        for candidate in mac_candidates:
            if candidate.is_file():
                return candidate
    return None


def validate_args(args: argparse.Namespace) -> tuple[Path, Path, Path | None]:
    source = resolve_existing(args.input, "Input video")
    output = args.output.expanduser().resolve()
    subtitle = None
    if subtitle_path := args.subtitle:
        subtitle = resolve_existing(subtitle_path, "Subtitle file")
        if subtitle.suffix.lower() not in SUBTITLE_SUFFIXES:
            raise RuntimeError("Subtitle must be ASS, SSA, SRT, or VTT.")
    if source == output:
        raise RuntimeError("Output path must differ from input video.")
    if output.suffix.lower() != ".mp4":
        raise RuntimeError("Output must use the .mp4 extension.")
    if output.exists() and not args.overwrite:
        raise RuntimeError("Output already exists. Ask the user to confirm replacement, then add --overwrite.")
    if not 0.05 <= args.watermark_opacity <= 1.0:
        raise RuntimeError("--watermark-opacity must be between 0.05 and 1.0.")
    if args.disclaimer_text and not 0.5 <= args.disclaimer_seconds <= 10:
        raise RuntimeError("--disclaimer-seconds must be between 0.5 and 10 seconds when a disclaimer is used.")
    if args.font:
        args.font = resolve_existing(args.font, "Font file")
    elif args.disclaimer_text or args.watermark_text:
        args.font = default_font()
        if not args.font:
            raise RuntimeError("A font file is required for disclaimer or watermark text. Pass --font /absolute/path/to/font.ttf.")
    return source, output, subtitle


def filter_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", r"\'").replace(":", r"\:").replace(",", r"\,").replace("[", r"\[").replace("]", r"\]").replace("\n", r"\n")


def font_option(font: Path | None) -> str:
    if font:
        return f"fontfile='{filter_escape(str(font))}'"
    return "font='Arial'"


def watermark_position(mode: str) -> tuple[str, str]:
    positions = {
        "top-right": ("w-tw-48", "48"),
        "top-left": ("48", "48"),
        "bottom-right": ("w-tw-48", "h-th-48"),
        "bottom-left": ("48", "h-th-48"),
        "drift": (r"mod(t*48\,w-tw)", "48+10*sin(t*0.8)"),
    }
    return positions[mode]


def build_video_filter(args: argparse.Namespace, subtitle: Path | None) -> str | None:
    filters: list[str] = []
    if subtitle:
        filters.append(f"subtitles=filename='{filter_escape(str(subtitle))}':charenc=UTF-8")
    if args.disclaimer_text:
        color = "black@1" if args.disclaimer_mode == "full-screen" else "black@0.72"
        enabled = f"between(t\\,0\\,{args.disclaimer_seconds:g})"
        filters.append(f"drawbox=x=0:y=0:w=iw:h=ih:color={color}:t=fill:enable='{enabled}'")
        filters.append(
            "drawtext="
            f"{font_option(args.font)}:text='{filter_escape(args.disclaimer_text)}':"
            "fontcolor=white:fontsize=h/24:borderw=1:bordercolor=black@0.5:"
            "x=(w-text_w)/2:y=(h-text_h)/2:"
            f"enable='{enabled}'"
        )
    if args.watermark_text:
        x, y = watermark_position(args.watermark_mode)
        filters.append(
            "drawtext="
            f"{font_option(args.font)}:text='{filter_escape(args.watermark_text)}':"
            f"fontcolor=white@{args.watermark_opacity:g}:fontsize=h/30:borderw=2:bordercolor=black@0.35:"
            f"x={x}:y={y}"
        )
    return ",".join(filters) if filters else None


def has_encoder(ffmpeg: str, encoder: str) -> bool:
    result = subprocess.run([ffmpeg, "-hide_banner", "-encoders"], check=False, capture_output=True, text=True)
    return encoder in result.stdout


def choose_encoder(ffmpeg: str, requested: str) -> str:
    if requested == "auto":
        return "h264_videotoolbox" if sys.platform == "darwin" and has_encoder(ffmpeg, "h264_videotoolbox") else "libx264"
    if not has_encoder(ffmpeg, requested):
        raise RuntimeError(f"Requested FFmpeg encoder is unavailable: {requested}")
    return requested


def encoder_options(encoder: str, quality: str) -> list[str]:
    if encoder == "h264_videotoolbox":
        bitrate = "18M" if quality == "high" else "12M"
        return ["-c:v", encoder, "-b:v", bitrate, "-maxrate", bitrate]
    crf = "18" if quality == "high" else "21"
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", crf]


def build_command(args: argparse.Namespace, source: Path, output: Path, subtitle: Path | None, ffmpeg: str) -> tuple[list[str], str]:
    encoder = choose_encoder(ffmpeg, args.encoder)
    command = [ffmpeg, "-hide_banner", "-y" if args.overwrite else "-n"]
    if args.trim_start:
        command.extend(["-ss", args.trim_start])
    command.extend(["-i", str(source)])
    if args.trim_duration:
        command.extend(["-t", args.trim_duration])
    video_filter = build_video_filter(args, subtitle)
    if video_filter:
        command.extend(["-vf", video_filter])
    command.extend(["-map", "0:v:0", "-map", "0:a?", "-map_metadata", "0"])
    command.extend(encoder_options(encoder, args.quality))
    if args.mute_disclaimer_audio:
        command.extend(["-af", f"volume=enable='between(t,0,{args.disclaimer_seconds:g})':volume=0", "-c:a", "aac", "-b:a", "192k"])
    else:
        command.extend(["-c:a", "copy"])
    command.extend(["-movflags", "+faststart", str(output)])
    return command, encoder


def main() -> int:
    args = parse_args()
    source, output, subtitle = validate_args(args)
    required_filters: set[str] = set()
    if subtitle:
        required_filters.add("subtitles")
    if args.disclaimer_text or args.watermark_text:
        required_filters.add("drawtext")
    ffmpeg, _ffprobe = require_ffmpeg(required_filters)
    output.parent.mkdir(parents=True, exist_ok=True)
    command, encoder = build_command(args, source, output, subtitle, ffmpeg)
    if args.dry_run:
        print(json.dumps({"command": command, "encoder": encoder, "output": str(output)}, ensure_ascii=False, indent=2))
        return 0
    subprocess.run(command, check=True)
    print(json.dumps({"output": str(output), "encoder": encoder, "size_bytes": output.stat().st_size}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        print(f"video-publish: {error}", file=sys.stderr)
        raise SystemExit(2)
