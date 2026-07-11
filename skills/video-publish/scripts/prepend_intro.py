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
    parser = argparse.ArgumentParser(description="Prepend a disclaimer while stream-copying the source video body.")
    parser.add_argument("input", type=Path, help="Source MP4 video.")
    parser.add_argument("--disclaimer-image", type=Path, default=DEFAULT_DISCLAIMER, help="Disclaimer image, defaults to the bundled asset.")
    parser.add_argument("--output", type=Path, required=True, help="Output MP4 path.")
    parser.add_argument("--disclaimer-seconds", type=float, default=3.0, help="Disclaimer duration, default 3 seconds.")
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


def validate_args(args: argparse.Namespace) -> tuple[Path, Path, Path]:
    source = resolve_file(args.input, "Source video")
    disclaimer = resolve_file(args.disclaimer_image, "Disclaimer image")
    output = args.output.expanduser().resolve()
    if source == output:
        raise RuntimeError("Output path must differ from the source video.")
    if output.suffix.lower() != ".mp4":
        raise RuntimeError("Output must use the .mp4 extension.")
    if output.exists() and not args.overwrite:
        raise RuntimeError("Output already exists. Confirm replacement, then add --overwrite.")
    if not 0.5 <= args.disclaimer_seconds <= 10:
        raise RuntimeError("--disclaimer-seconds must be between 0.5 and 10 seconds.")
    if args.preview_content_seconds is not None and args.preview_content_seconds <= 0:
        raise RuntimeError("--preview-content-seconds must be greater than zero.")
    return source, disclaimer, output


def build_intro_command(
    ffmpeg: str,
    disclaimer: Path,
    intro: Path,
    media: dict[str, object],
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
    intro_seconds = disclaimer_seconds
    gop = max(1, round(fps))
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
        f"{disclaimer_seconds:g}",
        "-i",
        str(disclaimer),
        "-f",
        "lavfi",
        "-t",
        f"{intro_seconds:g}",
        "-i",
        f"anullsrc=r={sample_rate}:cl={channel_layout}",
        "-vf",
        scale,
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-t",
        f"{intro_seconds:g}",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-qp",
        "26",
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
        "-x264-params",
        f"ref=3:b-pyramid=none:keyint={gop}:min-keyint={gop}:scenecut=0:chroma-qp-offset=0",
        "-c:a",
        "aac",
        "-b:a",
        f"{audio_bitrate}",
        "-ar",
        str(sample_rate),
        "-ac",
        str(channels),
    ]
    command.extend(["-mpegts_flags", "+initial_discontinuity", "-f", "mpegts", str(intro)])
    return command


def build_source_transport_command(
    ffmpeg: str,
    source: Path,
    media: dict[str, object],
    intro_seconds: float,
    preview_content_seconds: float | None,
) -> list[str]:
    fps = float(Fraction(str(media["video"]["r_frame_rate"])))
    # H.264 DTS can lead PTS by two frames. Offset the source beyond the intro
    # so the remuxer receives strictly increasing timestamps at the boundary.
    timestamp_offset = intro_seconds + (2 / fps) + (1 / 90_000)
    command = [ffmpeg, "-hide_banner", "-i", str(source)]
    if preview_content_seconds is not None:
        command.extend(["-t", f"{preview_content_seconds:g}"])
    command.extend(
        [
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-c",
            "copy",
            "-bsf:v",
            "h264_mp4toannexb",
            "-output_ts_offset",
            f"{timestamp_offset:.9f}",
            "-mpegts_flags",
            "+initial_discontinuity",
            "-f",
            "mpegts",
            "pipe:1",
        ]
    )
    return command


def build_mux_command(ffmpeg: str, output: Path, overwrite: bool) -> list[str]:
    return [
        ffmpeg,
        "-hide_banner",
        "-y" if overwrite else "-n",
        "-f",
        "mpegts",
        "-i",
        "pipe:0",
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-c",
        "copy",
        "-bsf:a",
        "aac_adtstoasc",
        "-movflags",
        "+faststart",
        str(output),
    ]


def stream_transport_concat(intro: Path, source_command: list[str], mux_command: list[str]) -> None:
    mux = subprocess.Popen(mux_command, stdin=subprocess.PIPE)
    if mux.stdin is None:
        raise RuntimeError("Could not open the final FFmpeg input pipe.")
    source_process: subprocess.Popen[bytes] | None = None
    try:
        with intro.open("rb") as intro_file:
            shutil.copyfileobj(intro_file, mux.stdin)
        source_process = subprocess.Popen(source_command, stdout=subprocess.PIPE)
        if source_process.stdout is None:
            raise RuntimeError("Could not open the source FFmpeg output pipe.")
        with source_process.stdout:
            shutil.copyfileobj(source_process.stdout, mux.stdin)
        source_result = source_process.wait()
        mux.stdin.close()
        mux_result = mux.wait()
    except Exception:
        if source_process and source_process.poll() is None:
            source_process.terminate()
        if mux.poll() is None:
            mux.terminate()
        raise
    if source_result != 0:
        raise RuntimeError(f"Source stream copy failed with exit code {source_result}.")
    if mux_result != 0:
        raise RuntimeError(f"Final MP4 mux failed with exit code {mux_result}.")


def main() -> int:
    args = parse_args()
    source, disclaimer, output = validate_args(args)
    ffmpeg, ffprobe = require_tools()
    media = probe_media(ffprobe, source)
    output.parent.mkdir(parents=True, exist_ok=True)
    intro_seconds = args.disclaimer_seconds
    with tempfile.TemporaryDirectory(prefix="video-publish-intro-") as temp_dir:
        temp_path = Path(temp_dir)
        intro = temp_path / "intro.ts"
        intro_command = build_intro_command(ffmpeg, disclaimer, intro, media, args.disclaimer_seconds)
        source_command = build_source_transport_command(ffmpeg, source, media, intro_seconds, args.preview_content_seconds)
        mux_command = build_mux_command(ffmpeg, output, args.overwrite)
        if args.dry_run:
            print(
                json.dumps(
                    {"intro_command": intro_command, "source_command": source_command, "mux_command": mux_command},
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
        subprocess.run(intro_command, check=True)
        stream_transport_concat(intro, source_command, mux_command)
    print(
        json.dumps(
            {
                "output": str(output),
                "disclaimer_image": str(disclaimer),
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
