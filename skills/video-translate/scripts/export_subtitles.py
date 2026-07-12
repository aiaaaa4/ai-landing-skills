#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from common import ass_escape, ass_time, display_chinese_subtitle_text, read_json, split_chinese_line, srt_time


ASS_HEADER = """[Script Info]
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,42,&H00FFFFFF,&H000000FF,&H00111111,&HAA000000,0,0,0,0,100,100,0,0,1,2,1,2,80,80,72,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export aligned subtitles.")
    parser.add_argument("aligned_segments", type=Path)
    parser.add_argument("--out-dir", type=Path, default=Path("runs/subtitles"))
    parser.add_argument("--basename", default="subtitles")
    parser.add_argument("--source-first", action="store_true", help="Put source line above Chinese line.")
    parser.add_argument("--zh-chars-per-line", type=float, default=36.0, help="Manual Chinese wrap width.")
    return parser.parse_args()



def subtitle_lines(segment: dict, source_first: bool, zh_chars_per_line: float) -> list[str]:
    source = segment["source_display"]
    translation_lines = split_chinese_line(display_chinese_subtitle_text(segment["translation"]), zh_chars_per_line)
    return [source, *translation_lines] if source_first else [*translation_lines, source]


def srt_text(segments: list[dict], source_first: bool, zh_chars_per_line: float) -> str:
    blocks = []
    for i, segment in enumerate(segments, start=1):
        lines = subtitle_lines(segment, source_first, zh_chars_per_line)
        blocks.append(
            f"{i}\n{srt_time(segment['start'])} --> {srt_time(segment['end'])}\n" + "\n".join(lines) + "\n"
        )
    return "\n".join(blocks)


def srt_bytes(segments: list[dict], source_first: bool, zh_chars_per_line: float) -> bytes:
    """Encode standard multiline SubRip cues with CRLF line endings."""
    text = srt_text(segments, source_first, zh_chars_per_line)
    return text.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8")


def ass_text(segments: list[dict], source_first: bool, zh_chars_per_line: float) -> str:
    events = []
    for segment in segments:
        source = ass_escape(segment["source_display"])
        translation = r"\N".join(ass_escape(line) for line in split_chinese_line(display_chinese_subtitle_text(segment["translation"]), zh_chars_per_line))
        start = ass_time(segment["start"])
        end = ass_time(segment["end"])
        if source_first:
            text = r"{\fs24}" + source + r"\N{\fs42}" + translation
        else:
            text = r"{\fs42}" + translation + r"\N{\fs24}" + source
        events.append(
            "Dialogue: 0,"
            f"{start},{end},"
            f"Default,,0,0,0,,{text}"
        )
    return ASS_HEADER + "\n".join(events) + "\n"


def main() -> int:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    payload = read_json(args.aligned_segments)
    segments = payload["segments"] if isinstance(payload, dict) else payload

    srt_path = args.out_dir / f"{args.basename}.srt"
    ass_path = args.out_dir / f"{args.basename}.ass"
    srt_path.write_bytes(srt_bytes(segments, args.source_first, args.zh_chars_per_line))
    ass_path.write_text(ass_text(segments, args.source_first, args.zh_chars_per_line), encoding="utf-8")
    print(f"Wrote {srt_path}")
    print(f"Wrote {ass_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
