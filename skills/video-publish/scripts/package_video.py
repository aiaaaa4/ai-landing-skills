#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
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
    parser.add_argument(
        "--max-size-multiplier",
        type=float,
        default=None,
        help="Optional strict output-size cap relative to the source file, for example 3.",
    )
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
    if args.max_size_multiplier is not None and args.max_size_multiplier <= 0:
        raise RuntimeError("--max-size-multiplier must be greater than zero.")
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


def display_width(character: str) -> int:
    return 2 if unicodedata.east_asian_width(character) in {"W", "F"} else 1


def wrap_disclaimer_text(value: str, max_width: int = 90) -> str:
    """Wrap mixed Chinese and Latin text using approximate display width."""
    lines: list[str] = []
    for paragraph in value.splitlines():
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        current = ""
        current_width = 0
        pending_space = ""
        tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9'()/-]*|\s+|.", paragraph)
        for token in tokens:
            if token.isspace():
                if current:
                    pending_space = " "
                continue
            prefix = pending_space if current else ""
            width = sum(display_width(character) for character in prefix + token)
            if current and current_width + width > max_width:
                lines.append(current.rstrip())
                current = token
                current_width = 0
                pending_space = ""
            else:
                current += prefix + token
            current_width += width
            pending_space = ""
        if current:
            lines.append(current.rstrip())
    return "\n".join(lines)


def build_video_filter(args: argparse.Namespace, subtitle: Path | None, disclaimer_file: Path | None = None) -> str | None:
    filters: list[str] = []
    if subtitle:
        filters.append(f"subtitles=filename='{filter_escape(str(subtitle))}':charenc=UTF-8")
    if args.disclaimer_text:
        color = "black@1" if args.disclaimer_mode == "full-screen" else "black@0.72"
        enabled = f"between(t\\,0\\,{args.disclaimer_seconds:g})"
        disclaimer_text = wrap_disclaimer_text(args.disclaimer_text)
        disclaimer_fontsize = "h/36" if disclaimer_text.count("\n") >= 8 else "h/24"
        disclaimer_source = (
            f"textfile='{filter_escape(str(disclaimer_file))}'"
            if disclaimer_file
            else f"text='{filter_escape(disclaimer_text)}'"
        )
        filters.append(f"drawbox=x=0:y=0:w=iw:h=ih:color={color}:t=fill:enable='{enabled}'")
        filters.append(
            "drawtext="
            f"{font_option(args.font)}:{disclaimer_source}:"
            f"fontcolor=white:fontsize={disclaimer_fontsize}:line_spacing=7:borderw=1:bordercolor=black@0.5:"
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
        raise RuntimeError("Could not read the input video duration for the size limit.") from error
    if duration <= 0:
        raise RuntimeError("Input video duration must be greater than zero for the size limit.")
    return duration


def constrained_bitrates(source: Path, duration: float, multiplier: float) -> tuple[int, int]:
    """Reserve room for audio and container overhead before setting a video bitrate."""
    total_budget = source.stat().st_size * multiplier * 8 / duration
    audio_bitrate = 160_000
    video_bitrate = int(total_budget * 0.92 - audio_bitrate)
    if video_bitrate < 300_000:
        raise RuntimeError("The requested output-size limit is too small for this video's duration.")
    return video_bitrate, audio_bitrate


def encoder_options(encoder: str, quality: str, target_video_bitrate: int | None = None) -> list[str]:
    if target_video_bitrate is not None:
        bitrate = f"{target_video_bitrate // 1000}k"
        if encoder == "h264_videotoolbox":
            return ["-c:v", encoder, "-b:v", bitrate, "-maxrate", bitrate]
        return ["-c:v", "libx264", "-preset", "veryfast", "-b:v", bitrate, "-maxrate", bitrate, "-bufsize", bitrate]
    if encoder == "h264_videotoolbox":
        bitrate = "18M" if quality == "high" else "12M"
        return ["-c:v", encoder, "-b:v", bitrate, "-maxrate", bitrate]
    crf = "18" if quality == "high" else "21"
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", crf]


def build_command(
    args: argparse.Namespace,
    source: Path,
    output: Path,
    subtitle: Path | None,
    ffmpeg: str,
    disclaimer_file: Path | None = None,
    duration: float | None = None,
) -> tuple[list[str], str]:
    encoder = choose_encoder(ffmpeg, args.encoder)
    target_video_bitrate = None
    target_audio_bitrate = None
    if args.max_size_multiplier is not None:
        if duration is None:
            raise RuntimeError("A source duration is required when --max-size-multiplier is used.")
        target_video_bitrate, target_audio_bitrate = constrained_bitrates(source, duration, args.max_size_multiplier)
    command = [ffmpeg, "-hide_banner", "-y" if args.overwrite else "-n"]
    if args.trim_start:
        command.extend(["-ss", args.trim_start])
    command.extend(["-i", str(source)])
    if args.trim_duration:
        command.extend(["-t", args.trim_duration])
    video_filter = build_video_filter(args, subtitle, disclaimer_file)
    if video_filter:
        command.extend(["-vf", video_filter])
    command.extend(["-map", "0:v:0", "-map", "0:a?", "-map_metadata", "0"])
    command.extend(encoder_options(encoder, args.quality, target_video_bitrate))
    if args.mute_disclaimer_audio:
        command.extend(["-af", f"volume=enable='between(t,0,{args.disclaimer_seconds:g})':volume=0"])
    if args.mute_disclaimer_audio or target_audio_bitrate is not None:
        audio_bitrate = target_audio_bitrate or 192_000
        command.extend(["-c:a", "aac", "-b:a", f"{audio_bitrate // 1000}k"])
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
    ffmpeg, ffprobe = require_ffmpeg(required_filters)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="video-publish-") as temp_dir:
        disclaimer_file = None
        if args.disclaimer_text:
            disclaimer_file = Path(temp_dir) / "disclaimer.txt"
            disclaimer_file.write_text(wrap_disclaimer_text(args.disclaimer_text), encoding="utf-8")
        duration = probe_duration(ffprobe, source) if args.max_size_multiplier is not None else None
        command, encoder = build_command(args, source, output, subtitle, ffmpeg, disclaimer_file, duration)
        if args.dry_run:
            print(json.dumps({"command": command, "encoder": encoder, "output": str(output)}, ensure_ascii=False, indent=2))
            return 0
        subprocess.run(command, check=True)
    if args.max_size_multiplier is not None and output.stat().st_size > source.stat().st_size * args.max_size_multiplier:
        output.unlink()
        raise RuntimeError("Output exceeded the requested size limit and was removed.")
    print(json.dumps({"output": str(output), "encoder": encoder, "size_bytes": output.stat().st_size}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        print(f"video-publish: {error}", file=sys.stderr)
        raise SystemExit(2)
