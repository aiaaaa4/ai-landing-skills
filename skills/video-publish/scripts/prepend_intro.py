#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from fractions import Fraction
from pathlib import Path

from subtitle_timeline import default_subtitle_output, write_bcc_file


DEFAULT_DISCLAIMER = Path(__file__).resolve().parents[1] / "assets" / "disclaimer-zh-en-1920x1080.png"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepend a disclaimer while stream-copying the source video body.")
    parser.add_argument("input", type=Path, help="Source MP4 video.")
    parser.add_argument("--disclaimer-image", type=Path, default=DEFAULT_DISCLAIMER, help="Disclaimer image, defaults to the bundled asset.")
    parser.add_argument("--output", type=Path, required=True, help="Output MP4 path.")
    parser.add_argument("--subtitle", type=Path, default=None, help="Optional source-timeline bilingual SRT to shift for the packaged video.")
    parser.add_argument("--subtitle-output", type=Path, default=None, help="Optional release BCC path; defaults to the packaged-video naming rule.")
    parser.add_argument("--timeline-output", type=Path, default=None, help="Optional timeline manifest path; defaults beside the packaged video.")
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


def validate_args(args: argparse.Namespace) -> tuple[Path, Path, Path, Path | None, Path, Path | None]:
    source = resolve_file(args.input, "Source video")
    disclaimer = resolve_file(args.disclaimer_image, "Disclaimer image")
    output = args.output.expanduser().resolve()
    subtitle = resolve_file(args.subtitle, "Subtitle") if args.subtitle else None
    if subtitle and subtitle.suffix.lower() != ".srt":
        raise RuntimeError("Lightweight subtitle delivery currently supports SRT only.")
    if args.subtitle_output and not subtitle:
        raise RuntimeError("--subtitle-output requires --subtitle.")
    subtitle_output = (
        args.subtitle_output.expanduser().resolve()
        if args.subtitle_output
        else default_subtitle_output(source, output, subtitle) if subtitle else None
    )
    timeline_output = (
        args.timeline_output.expanduser().resolve()
        if args.timeline_output
        else output.parent / ".work" / "publish" / f"{output.stem}.timeline.json"
    )
    paths = [source, disclaimer, output, timeline_output]
    if subtitle:
        paths.append(subtitle)
    if subtitle_output:
        paths.append(subtitle_output)
    if len(paths) != len(set(paths)):
        raise RuntimeError("Source, subtitle, disclaimer, video output, subtitle output, and timeline output must use distinct paths.")
    if source == output:
        raise RuntimeError("Output path must differ from the source video.")
    if output.suffix.lower() != ".mp4":
        raise RuntimeError("Output must use the .mp4 extension.")
    if subtitle_output and subtitle_output.suffix.lower() != ".bcc":
        raise RuntimeError("Subtitle output must use the .bcc extension.")
    if timeline_output.suffix.lower() != ".json":
        raise RuntimeError("Timeline output must use the .json extension.")
    if output.exists() and not args.overwrite:
        raise RuntimeError("Output already exists. Confirm replacement, then add --overwrite.")
    for derived in (subtitle_output, timeline_output):
        if derived and derived.exists() and not args.overwrite:
            raise RuntimeError(f"Derived output already exists. Confirm replacement, then add --overwrite: {derived}")
    if not 0.5 <= args.disclaimer_seconds <= 10:
        raise RuntimeError("--disclaimer-seconds must be between 0.5 and 10 seconds.")
    if args.preview_content_seconds is not None and args.preview_content_seconds <= 0:
        raise RuntimeError("--preview-content-seconds must be greater than zero.")
    return source, disclaimer, output, subtitle, timeline_output, subtitle_output


def transport_offset_seconds(media: dict[str, object], intro_seconds: float) -> float:
    fps = float(Fraction(str(media["video"]["r_frame_rate"])))
    # H.264 DTS can lead PTS by two frames. The source transport starts after
    # that boundary guard, so companion subtitles must use the same offset.
    return intro_seconds + (2 / fps) + (1 / 90_000)


def decoded_frame_hashes(
    ffmpeg: str,
    path: Path,
    selector: str,
    seconds: float,
) -> tuple[Fraction, list[tuple[int, str]]]:
    result = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(path),
            "-t",
            f"{seconds:g}",
            "-map",
            f"0:{selector}:0",
            "-f",
            "framemd5",
            "-",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    time_base_match = re.search(r"^#tb 0:\s*(\d+/\d+)", result.stdout, re.MULTILINE)
    if not time_base_match:
        raise RuntimeError(f"Could not read {selector} frame time base for subtitle alignment.")
    frames: list[tuple[int, str]] = []
    for line in result.stdout.splitlines():
        if not line or line.startswith("#"):
            continue
        parts = [part.strip() for part in line.split(",")]
        if len(parts) >= 6:
            frames.append((int(parts[2]), parts[5]))
    return Fraction(time_base_match.group(1)), frames


def match_decoded_stream_offset(
    ffmpeg: str,
    source: Path,
    output: Path,
    selector: str,
    intro_seconds: float,
) -> float:
    source_time_base, source_frames = decoded_frame_hashes(ffmpeg, source, selector, 2)
    output_time_base, output_frames = decoded_frame_hashes(ffmpeg, output, selector, intro_seconds + 4)
    return find_frame_hash_offset(
        source_time_base,
        source_frames,
        output_time_base,
        output_frames,
        selector,
        intro_seconds,
    )


def find_frame_hash_offset(
    source_time_base: Fraction,
    source_frames: list[tuple[int, str]],
    output_time_base: Fraction,
    output_frames: list[tuple[int, str]],
    selector: str,
    intro_seconds: float,
) -> float:
    window = min(24, len(source_frames), len(output_frames))
    if window < 8:
        raise RuntimeError(f"Not enough decoded {selector} frames for subtitle alignment.")
    for source_index in range(min(80, len(source_frames) - window + 1)):
        source_hashes = [frame[1] for frame in source_frames[source_index : source_index + window]]
        if selector == "a" and len(set(source_hashes)) < 4:
            continue
        for output_index in range(len(output_frames) - window + 1):
            output_time = float(output_frames[output_index][0] * output_time_base)
            if output_time < intro_seconds - 0.25:
                continue
            if [frame[1] for frame in output_frames[output_index : output_index + window]] != source_hashes:
                continue
            source_time = float(source_frames[source_index][0] * source_time_base)
            offset = output_time - source_time
            if offset >= intro_seconds - 0.25:
                return offset
    raise RuntimeError(f"Could not match decoded {selector} content across the publish boundary.")


def probe_content_offset(
    ffmpeg: str,
    ffprobe: str,
    intro: Path,
    output: Path,
    source: Path,
    intro_seconds: float,
    has_audio: bool,
) -> tuple[float, str]:
    if has_audio:
        try:
            return match_decoded_stream_offset(ffmpeg, source, output, "a", intro_seconds), "audio-frame-match"
        except RuntimeError as error:
            print(f"Audio alignment fallback: {error}", file=sys.stderr)
    count_result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-count_frames",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=nb_read_frames",
            "-of",
            "json",
            str(intro),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    streams = json.loads(count_result.stdout).get("streams", [])
    if not streams or not streams[0].get("nb_read_frames"):
        raise RuntimeError("Could not count disclaimer frames for subtitle alignment.")
    intro_frame_count = int(streams[0]["nb_read_frames"])

    def frame_timestamps(path: Path, interval_seconds: float) -> list[float]:
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-read_intervals",
                f"0%+{interval_seconds:g}",
                "-show_entries",
                "frame=best_effort_timestamp_time",
                "-of",
                "json",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return [
            float(frame["best_effort_timestamp_time"])
            for frame in json.loads(result.stdout).get("frames", [])
            if frame.get("best_effort_timestamp_time") is not None
        ]

    output_timestamps = frame_timestamps(output, intro_seconds + 2)
    source_timestamps = frame_timestamps(source, 1)
    if len(output_timestamps) <= intro_frame_count or not source_timestamps:
        raise RuntimeError("Could not locate the source-video boundary for subtitle alignment.")
    offset = output_timestamps[intro_frame_count] - source_timestamps[0]
    if offset < 0:
        raise RuntimeError("Detected a negative source-video offset; refusing to rewrite subtitles.")
    return offset, "video-frame-boundary"


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
    timestamp_offset = transport_offset_seconds(media, intro_seconds)
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
    source, disclaimer, output, subtitle, timeline_output, subtitle_output = validate_args(args)
    ffmpeg, ffprobe = require_tools()
    media = probe_media(ffprobe, source)
    output.parent.mkdir(parents=True, exist_ok=True)
    intro_seconds = args.disclaimer_seconds
    transport_offset = transport_offset_seconds(media, intro_seconds)
    with tempfile.TemporaryDirectory(prefix="video-publish-intro-") as temp_dir:
        temp_path = Path(temp_dir)
        intro = temp_path / "intro.ts"
        intro_command = build_intro_command(ffmpeg, disclaimer, intro, media, args.disclaimer_seconds)
        source_command = build_source_transport_command(ffmpeg, source, media, intro_seconds, args.preview_content_seconds)
        mux_command = build_mux_command(ffmpeg, output, args.overwrite)
        if args.dry_run:
            print(
                json.dumps(
                    {
                        "intro_command": intro_command,
                        "source_command": source_command,
                        "mux_command": mux_command,
                        "estimated_content_offset_seconds": args.disclaimer_seconds,
                        "transport_offset_seconds": transport_offset,
                        "subtitle_output": str(subtitle_output) if subtitle_output else None,
                        "timeline_output": str(timeline_output),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
        subprocess.run(intro_command, check=True)
        stream_transport_concat(intro, source_command, mux_command)
        content_offset, offset_basis = probe_content_offset(
            ffmpeg,
            ffprobe,
            intro,
            output,
            source,
            intro_seconds,
            media["audio"] is not None,
        )
    if subtitle and subtitle_output:
        subtitle_output.parent.mkdir(parents=True, exist_ok=True)
        write_bcc_file(subtitle, subtitle_output, content_offset)
    timeline_output.parent.mkdir(parents=True, exist_ok=True)
    timeline_output.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "source_video": str(source),
                "packaged_video": str(output),
                "source_subtitle": str(subtitle) if subtitle else None,
                "packaged_subtitle": str(subtitle_output) if subtitle_output else None,
                "packaged_subtitle_format": "bcc" if subtitle_output else None,
                "disclaimer_seconds": args.disclaimer_seconds,
                "content_offset_seconds": content_offset,
                "offset_basis": offset_basis,
                "source_video_reencoded": False,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(output),
                "disclaimer_image": str(disclaimer),
                "disclaimer_seconds": args.disclaimer_seconds,
                "content_offset_seconds": content_offset,
                "offset_basis": offset_basis,
                "subtitle_output": str(subtitle_output) if subtitle_output else None,
                "timeline_output": str(timeline_output),
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
        print(f"video-publish: {error}", file=sys.stderr)
        raise SystemExit(2)
