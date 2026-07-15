#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path


TIMESTAMP_PATTERN = re.compile(
    r"(?P<start>\d{2,}:\d{2}:\d{2},\d{3})\s*-->\s*(?P<end>\d{2,}:\d{2}:\d{2},\d{3})"
)


def timestamp_to_milliseconds(value: str) -> int:
    hours, minutes, remainder = value.split(":")
    seconds, milliseconds = remainder.split(",")
    return (((int(hours) * 60 + int(minutes)) * 60) + int(seconds)) * 1000 + int(milliseconds)


def milliseconds_to_timestamp(value: int) -> str:
    if value < 0:
        raise ValueError("Subtitle timestamps cannot be negative.")
    hours, remainder = divmod(value, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def shift_srt_text(text: str, offset_seconds: float) -> str:
    offset_ms = round(offset_seconds * 1000)
    if offset_ms < 0:
        raise ValueError("Only non-negative prepend offsets are supported.")

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    matches = 0
    shifted_lines: list[str] = []
    for line in normalized.splitlines():
        match = TIMESTAMP_PATTERN.fullmatch(line.strip())
        if not match:
            shifted_lines.append(line)
            continue
        matches += 1
        start = timestamp_to_milliseconds(match.group("start")) + offset_ms
        end = timestamp_to_milliseconds(match.group("end")) + offset_ms
        shifted_lines.append(f"{milliseconds_to_timestamp(start)} --> {milliseconds_to_timestamp(end)}")
    if matches == 0:
        raise ValueError("No valid SRT timestamp lines were found.")
    return "\n".join(shifted_lines).rstrip("\n") + "\n"


def shift_srt_file(source: Path, output: Path, offset_seconds: float) -> None:
    text = source.read_text(encoding="utf-8-sig")
    shifted = shift_srt_text(text, offset_seconds)
    output.write_bytes(shifted.replace("\n", "\r\n").encode("utf-8"))


def srt_to_bcc_payload(text: str, offset_seconds: float) -> dict[str, object]:
    offset_ms = round(offset_seconds * 1000)
    if offset_ms < 0:
        raise ValueError("Only non-negative prepend offsets are supported.")

    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    body: list[dict[str, object]] = []
    for block in re.split(r"\n{2,}", normalized):
        lines = block.splitlines()
        timestamp_index = next(
            (index for index, line in enumerate(lines) if TIMESTAMP_PATTERN.fullmatch(line.strip())),
            None,
        )
        if timestamp_index is None:
            continue
        match = TIMESTAMP_PATTERN.fullmatch(lines[timestamp_index].strip())
        if match is None:
            continue
        content = "\n".join(lines[timestamp_index + 1 :]).strip()
        if not content:
            raise ValueError("BCC conversion found an SRT cue without subtitle text.")
        start = timestamp_to_milliseconds(match.group("start")) + offset_ms
        end = timestamp_to_milliseconds(match.group("end")) + offset_ms
        if end <= start:
            raise ValueError("BCC conversion found a subtitle cue whose end is not after its start.")
        body.append(
            {
                "from": round(start / 1000, 3),
                "to": round(end / 1000, 3),
                "location": 2,
                "content": content,
            }
        )
    if not body:
        raise ValueError("No valid SRT subtitle cues were found.")
    return {
        "font_size": 0.4,
        "font_color": "#FFFFFF",
        "background_alpha": 0.5,
        "background_color": "#9C27B0",
        "Stroke": "none",
        "body": body,
    }


def write_bcc_file(source: Path, output: Path, offset_seconds: float) -> None:
    text = source.read_text(encoding="utf-8-sig")
    payload = srt_to_bcc_payload(text, offset_seconds)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def default_subtitle_output(source_video: Path, output_video: Path, subtitle: Path) -> Path:
    source_stem = source_video.stem
    subtitle_stem = subtitle.stem
    if subtitle_stem == source_stem:
        derived_stem = output_video.stem
    elif subtitle_stem.startswith(source_stem + "."):
        derived_stem = output_video.stem + subtitle_stem[len(source_stem):]
    else:
        derived_stem = subtitle_stem + "-发布版"
    return output_video.parent / f"{derived_stem}.bcc"
