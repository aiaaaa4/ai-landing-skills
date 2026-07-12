#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import os
import re
import shutil
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

from common import read_json, write_json


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GLOSSARY = PROJECT_ROOT / "references" / "trading_glossary.md"
DEFAULT_TERM_RULES = PROJECT_ROOT / "references" / "term_repair_rules.json"
NORMAL_WORD_LIMIT = 20_000
LONG_WORD_LIMIT = 50_000
AUDIO_SUFFIXES = (".m4a", ".mp3", ".aac", ".wav", ".flac", ".ogg", ".opus")
VIDEO_SUFFIXES = (
    ".mp4", ".mkv", ".mov", ".webm", ".avi", ".m4v", ".mpeg",
    ".mpg", ".ts", ".mts", ".m2ts", ".flv", ".wmv", ".3gp",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the fixed video subtitle workflow: ffmpeg -> OkFile -> Fun-ASR -> qwen-mt-plus helper segments -> subtitles."
    )
    parser.add_argument("media", type=Path, help="Input local video file. Direct audio input is not supported.")
    parser.add_argument(
        "--language",
        default="en",
        help="Source language hint for ASR, for example en, fr, es, it. Translation target is always Chinese.",
    )
    parser.add_argument("--run-id", default=None, help="Run directory name. Defaults to a slug from the media name.")
    parser.add_argument(
        "--runs-dir",
        type=Path,
        default=None,
        help="Working directory. Defaults to .work/<run-id> inside the subtitle output directory.",
    )
    parser.add_argument("--outputs-dir", type=Path, default=None)
    parser.add_argument(
        "--source-subtitle",
        type=Path,
        default=None,
        help="Optional original-language SRT/VTT used to correct ASR text while preserving Fun-ASR word timestamps.",
    )
    parser.add_argument(
        "--keep-workflow-inputs",
        action="store_true",
        help="Keep downloader-created files under .work/input after successful export for debugging.",
    )
    parser.add_argument("--segments", type=Path, default=None, help="Optional completed segments.txt to copy in.")
    parser.add_argument(
        "--subtitle-tag",
        dest="subtitle_tag",
        default=None,
        help="Suffix appended to the original video filename. Defaults to zh-<source-language>.",
    )
    parser.add_argument("--bilingual-tag", dest="subtitle_tag", help=argparse.SUPPRESS)
    parser.add_argument(
        "--domain-name",
        default="finance/trading training videos",
        help="Domain/style label injected into AI prompts.",
    )
    parser.add_argument(
        "--glossary",
        type=Path,
        default=DEFAULT_GLOSSARY,
        help="Domain glossary/style guide injected into AI prompts.",
    )
    parser.add_argument(
        "--term-rules",
        type=Path,
        default=DEFAULT_TERM_RULES,
        help="Automatic repair rules for SRC_DISPLAY and ZH.",
    )
    parser.add_argument(
        "--disable-domain-term-checks",
        action="store_true",
        help="Disable built-in finance/trading bad-term QA warnings for non-trading domains.",
    )
    parser.add_argument("--source-first", action="store_true", help="Put source line above Chinese line.")
    parser.add_argument("--orchestrator-model", default=None, help="Name of the AI model orchestrating this run, for the final chat summary.")
    parser.add_argument("--translation-model", default="qwen-mt-plus", help="Name of the model used for segments.txt. Production default: qwen-mt-plus.")
    parser.add_argument(
        "--confirm-external-processing",
        action="store_true",
        help="Required acknowledgement before audio prepared from the selected video is sent to OkFile and Alibaba services.",
    )
    parser.add_argument("--skip-env-check", action="store_true")
    return parser.parse_args()


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-")
    return value[:80] or "video"


def language_slug(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-")
    return value or "src"


def default_subtitle_tag(language: str) -> str:
    source_labels = {
        "en": "英",
        "eng": "英",
        "english": "英",
        "fr": "法",
        "fra": "法",
        "fre": "法",
        "french": "法",
        "es": "西",
        "spa": "西",
        "spanish": "西",
        "it": "意",
        "ita": "意",
        "italian": "意",
    }
    return f"中{source_labels.get(language.lower().strip(), language_slug(language))}双语字幕"


def resolve_asr_media(media: Path) -> Path:
    """Reuse a downloader-provided sibling audio file when it matches the media basename."""
    if media.suffix.lower() in AUDIO_SUFFIXES:
        return media
    hidden_input = media.parent / ".work" / "input"
    for suffix in AUDIO_SUFFIXES:
        candidate = hidden_input / f"{media.stem}{suffix}"
        if candidate.exists() and candidate.stat().st_size > 0:
            return candidate
    for suffix in AUDIO_SUFFIXES:
        candidate = media.with_suffix(suffix)
        if candidate.exists() and candidate.stat().st_size > 0:
            return candidate
    return media


def resolve_source_subtitle(media: Path, explicit: Path | None) -> Path | None:
    if explicit:
        resolved = explicit.expanduser().resolve()
        if not resolved.is_file():
            raise RuntimeError(f"Source subtitle reference was not found: {resolved}")
        if resolved.suffix.lower() not in {".srt", ".vtt"}:
            raise RuntimeError("Source subtitle reference must be SRT or VTT.")
        return resolved
    hidden_input = media.parent / ".work" / "input"
    preferred = [
        hidden_input / f"{media.stem}.原语言字幕.srt",
        hidden_input / f"{media.stem}.原语言字幕.vtt",
    ]
    for candidate in preferred:
        if candidate.is_file() and candidate.stat().st_size > 0:
            return candidate.resolve()
    candidates = sorted(
        path.resolve()
        for suffix in (".srt", ".vtt")
        for path in hidden_input.glob(f"{media.stem}*{suffix}")
        if path.is_file() and "双语字幕" not in path.name
    )
    if len(candidates) > 1:
        raise RuntimeError(
            "Multiple source subtitle references were found under .work/input; "
            "keep one or pass --source-subtitle explicitly."
        )
    return candidates[0] if candidates else None


def cleanup_workflow_inputs(media: Path, paths: list[Path | None]) -> list[Path]:
    input_root = (media.parent / ".work" / "input").resolve()
    removed: list[Path] = []
    for path in {item.resolve() for item in paths if item and item.exists()}:
        if path == media or not path.is_relative_to(input_root):
            continue
        path.unlink()
        removed.append(path)
    if input_root.is_dir() and not any(input_root.iterdir()):
        input_root.rmdir()
    return sorted(removed)


def default_outputs_dir() -> Path:
    if PROJECT_ROOT.name == "work":
        return PROJECT_ROOT.parent / "outputs"
    if PROJECT_ROOT.parent.name == "work":
        return PROJECT_ROOT.parents[1] / "outputs"
    return PROJECT_ROOT / "outputs"


def run_step(args: list[str], *, cwd: Path = PROJECT_ROOT) -> None:
    print("+ " + " ".join(args), flush=True)
    subprocess.run(args, cwd=cwd, check=True)


def run_step_status(args: list[str], *, cwd: Path = PROJECT_ROOT) -> int:
    print("+ " + " ".join(args), flush=True)
    return subprocess.run(args, cwd=cwd, check=False).returncode


def media_duration_seconds(media: Path) -> float | None:
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(media),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return float(proc.stdout.strip())
    except Exception:
        return None


def print_run_expectation(media: Path) -> None:
    duration = media_duration_seconds(media)
    if duration is None:
        print("Duration: unknown; long runs should still send user-facing heartbeat updates every 10 minutes.", flush=True)
        return
    minutes = duration / 60
    low = max(5.0, minutes * 0.25)
    high = max(low + 2.0, minutes * 0.75)
    print(f"Duration: {minutes:.1f} min", flush=True)
    print(
        f"Rough first-run estimate: {low:.0f}-{high:.0f} min before AI repair/QA; "
        "actual time depends on upload speed, Alibaba queueing, AI model speed, and whether screen context is enabled.",
        flush=True,
    )
    print("User-facing heartbeat policy: for runs expected over 10 minutes, report status every 10 minutes.", flush=True)


def model_name_from_env(explicit: str | None = None) -> str:
    if explicit:
        return explicit
    return "current orchestrating AI (not recorded)"


def count_word_table(work_dir: Path) -> int | None:
    path = work_dir / "word_table.json"
    if not path.exists():
        return None
    try:
        payload = read_json(path)
    except Exception:
        return None
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict) and isinstance(payload.get("words"), list):
        return len(payload["words"])
    return None


def content_length_class(word_count: int | None) -> tuple[str, str]:
    if word_count is None:
        return "unknown", "Word count unavailable; use fixed qwen-mt-plus helper and rely on QA/export checks."
    if word_count <= NORMAL_WORD_LIMIT:
        return "normal", f"{word_count} words <= {NORMAL_WORD_LIMIT}; use fixed qwen-mt-plus helper for segmentation/translation."
    if word_count <= LONG_WORD_LIMIT:
        return "long", f"{word_count} words is long content; use fixed qwen-mt-plus helper with cache/concurrency."
    return "extra-long", f"{word_count} words > {LONG_WORD_LIMIT}; warn the user about cost/time and use fixed qwen-mt-plus helper with cache/concurrency."


def print_segment_generation_policy(work_dir: Path) -> None:
    word_count = count_word_table(work_dir)
    length_class, detail = content_length_class(word_count)
    print(f"ASR word count: {word_count if word_count is not None else 'unknown'}", flush=True)
    print(f"Content length class: {length_class}. {detail}", flush=True)
    print(
        "Segment generation policy: fixed production path uses Alibaba Bailian qwen-mt-plus helper for segments.txt. "
        "The orchestrating AI handles tool execution, timestamp alignment, QA repair, export, and the final chat summary.",
        flush=True,
    )
    write_json(
        work_dir / "segment_routing_policy.json",
        {
            "word_count": word_count,
            "length_class": length_class,
            "normal_word_limit": NORMAL_WORD_LIMIT,
            "long_word_limit": LONG_WORD_LIMIT,
            "segment_generation_path": "fixed DashScope helper",
            "fixed_helper_model": "qwen-mt-plus",
            "helper_fallback_model": "",
            "orchestrator_role": "tool execution, timestamp alignment, QA repair, subtitle export, and final chat summary",
        },
    )



def source_language_name(language: str) -> str:
    value = language.lower().strip()
    mapping = {
        "en": "English",
        "eng": "English",
        "english": "English",
        "fr": "French",
        "fra": "French",
        "fre": "French",
        "french": "French",
        "es": "Spanish",
        "spa": "Spanish",
        "spanish": "Spanish",
        "it": "Italian",
        "ita": "Italian",
        "italian": "Italian",
    }
    return mapping.get(value, language or "English")


def ensure_ai_segments(
    work_dir: Path,
    transcript_dir: Path,
    language: str,
    domain_name: str,
    source_subtitle: Path | None,
) -> None:
    segments = work_dir / "segments.txt"
    if segments.exists():
        meta_path = work_dir / "segment_generation_meta.json"
        if source_subtitle:
            if not meta_path.exists():
                raise RuntimeError(
                    "Existing segments have no source-reference metadata. "
                    "Use a new --run-id so corrected text and cached translations cannot mix."
                )
            meta = read_json(meta_path)
            previous = str(meta.get("source_subtitle") or "")
            previous_hash = str(meta.get("source_subtitle_sha256") or "")
            current_hash = hashlib.sha256(source_subtitle.read_bytes()).hexdigest()
            if previous != str(source_subtitle) or previous_hash != current_hash:
                raise RuntimeError(
                    "Existing segments were generated with a different source subtitle reference. "
                    "Use a new --run-id so corrected text and cached translations cannot mix."
                )
        print(f"Using existing segments: {segments}", flush=True)
        return

    screen_context = work_dir / "screen_context.txt"
    cmd = [
        sys.executable,
        "scripts/generate_segments_with_dashscope.py",
        str(transcript_dir / "transcript_words.json"),
        "--out",
        str(segments),
        "--cache",
        str(work_dir / "dashscope_translation_cache.json"),
        "--model",
        "auto",
        "--source-language-name",
        source_language_name(language),
        "--domain-name",
        domain_name,
        "--concurrency",
        "1",
        "--max-retries",
        "8",
        "--qwen-mt-min-interval-seconds",
        "1.0",
        "--confirm-external-processing",
    ]
    if screen_context.exists() and screen_context.stat().st_size > 0:
        cmd.extend(["--screen-context", str(screen_context)])
    if source_subtitle:
        cmd.extend(["--source-subtitle", str(source_subtitle)])
    run_step(cmd)


def ensure_transcript(media: Path, transcript_dir: Path, language: str, confirm_external_processing: bool) -> None:
    transcript_path = transcript_dir / "transcript_words.json"
    if transcript_path.exists():
        transcript = read_json(transcript_path)
        existing_language = str(transcript.get("language") or "").strip()
        if existing_language and existing_language != language:
            raise RuntimeError(
                f"Existing transcript was created with language={existing_language}, "
                f"but this run requested language={language}. Use a new --run-id or remove the old run directory."
            )
        print(f"Using existing transcript: {transcript_path}", flush=True)
        return

    run_step(
        [
            sys.executable,
            "scripts/transcribe_api.py",
            str(media),
            "--provider",
            "aliyun-fun-asr",
            "--out-dir",
            str(transcript_dir),
            "--language",
            language,
            "--confirm-external-processing",
        ]
    )


def ensure_work_files(transcript_dir: Path, work_dir: Path) -> None:
    word_table = work_dir / "word_table.json"
    word_stream = work_dir / "word_stream.txt"
    asr_reference = work_dir / "asr_segments_reference.txt"
    if word_table.exists() and word_stream.exists() and asr_reference.exists():
        print(f"Using existing word stream: {word_stream}", flush=True)
        print(f"Using existing ASR reference: {asr_reference}", flush=True)
        return

    run_step(
        [
            sys.executable,
            "scripts/extract_word_stream.py",
            str(transcript_dir / "transcript_words.json"),
            "--out-dir",
            str(work_dir),
        ]
    )


def file_fingerprint(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    stat = path.stat()
    return {"path": str(path), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def ensure_prompt(work_dir: Path, domain_name: str, glossary: Path) -> None:
    prompt = work_dir / "prompt.txt"
    meta_path = work_dir / "prompt_meta.json"
    asr_reference = work_dir / "asr_segments_reference.txt"
    screen_context = work_dir / "screen_context.txt"
    desired_meta = {
        "domain_name": domain_name,
        "glossary": str(glossary),
        "asr_reference": str(asr_reference),
        "screen_context": file_fingerprint(screen_context),
    }
    if prompt.exists() and meta_path.exists():
        if read_json(meta_path) == desired_meta:
            print(f"Using existing prompt: {prompt}", flush=True)
            return
        print("Prompt settings changed; regenerating prompt.", flush=True)
    elif prompt.exists():
        print("Prompt metadata missing; regenerating prompt with current workflow rules.", flush=True)

    run_step(
        [
            sys.executable,
            "scripts/generate_prompt.py",
            str(work_dir / "word_stream.txt"),
            "--out",
            str(prompt),
            "--asr-reference",
            str(asr_reference),
            "--domain-name",
            domain_name,
            "--glossary",
            str(glossary),
            "--screen-context",
            str(screen_context),
        ]
    )
    write_json(meta_path, desired_meta)


def maybe_copy_segments(source: Path | None, destination: Path) -> None:
    if source is None:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    print(f"Copied segments: {source} -> {destination}", flush=True)


def record_step_status(work_dir: Path, step: str, status: str, detail: str = "") -> None:
    status_path = work_dir / "workflow_status.json"
    payload = {"updated": dt.datetime.now().isoformat(timespec="seconds"), "steps": {}}
    if status_path.exists():
        try:
            existing = read_json(status_path)
            if isinstance(existing, dict):
                payload.update(existing)
                payload.setdefault("steps", {})
        except Exception:
            pass
    payload["updated"] = dt.datetime.now().isoformat(timespec="seconds")
    payload["steps"][step] = {"status": status, "detail": detail}
    write_json(status_path, payload)


def classify_failure(message: str) -> tuple[str, str, list[str]]:
    lower = message.lower()
    if "okfile" in lower:
        return (
            "VTZ-E003",
            "OkFile upload or URL failure",
            [
                "Check OKFILE_TOKEN, network access, upload quota, and whether the cached URL expired.",
                "Rerun with the same --run-id so completed local stages can be reused.",
            ],
        )
    if "dashscope" in lower or "aliyun" in lower or "workspace" in lower:
        return (
            "VTZ-E004",
            "Alibaba Fun-ASR / DashScope failure",
            [
                "Check DASHSCOPE_API_KEY, ALIYUN_WORKSPACE_ID, ALIYUN_REGION, account balance, and Alibaba task status.",
                "If a cached Alibaba task failed, rerun with the same --run-id; the workflow will resubmit when the previous task is terminal failed.",
            ],
        )
    if "ffmpeg" in lower:
        return (
            "VTZ-E002",
            "ffmpeg environment failure",
            [
                "Install ffmpeg and ensure it is available on PATH.",
                "Run python scripts/check_env.py after installation.",
            ],
        )
    if "segments.txt" in lower or "src_raw" in lower:
        return (
            "VTZ-E005",
            "AI segment contract failure",
            [
                "The AI runner should repair segments.txt using prompt.txt, final_qa_prompt.txt, and final_qa_report.md.",
                "Escalate for user review only after two automatic repair attempts still fail.",
            ],
        )
    return (
        "VTZ-E000",
        "Unclassified workflow failure",
        [
            "Review workflow_status.json and the latest script output in the run directory.",
            "Run python scripts/check_env.py --json if environment or secret configuration is uncertain.",
        ],
    )


def print_failure_guidance(error: Exception) -> None:
    message = str(error)
    code, title, checks = classify_failure(message)
    print("\nWorkflow failed.", file=sys.stderr)
    print(f"- Code: {code}", file=sys.stderr)
    print(f"- Category: {title}", file=sys.stderr)
    print(f"- Error: {message}", file=sys.stderr)
    print("- Next step: use the checklist below, then rerun the same command; completed stages are reused when possible.", file=sys.stderr)
    for check in checks:
        print(f"- {check}", file=sys.stderr)



def read_optional_json(path: Path) -> object | None:
    if not path.exists():
        return None
    try:
        return read_json(path)
    except Exception:
        return None


def record_step_timing(work_dir: Path, step: str, elapsed: float, detail: str = "") -> None:
    path = work_dir / "step_timings.json"
    payload = read_optional_json(path)
    if not isinstance(payload, dict):
        payload = {"steps": {}}
    payload.setdefault("steps", {})
    payload["steps"][step] = {
        "seconds": round(elapsed, 3),
        "minutes": round(elapsed / 60, 3),
        "detail": detail,
        "updated": dt.datetime.now().isoformat(timespec="seconds"),
    }
    write_json(path, payload)


def qa_summary_from_report(report_path: Path) -> tuple[list[str], dict[str, str], Counter[str]]:
    qa_summary: list[str] = []
    summary_counts: dict[str, str] = {}
    warning_types: Counter[str] = Counter()
    if not report_path.exists():
        return qa_summary, summary_counts, warning_types

    lines = report_path.read_text(encoding="utf-8").splitlines()
    in_summary = False
    for line in lines:
        if line.strip() == "## Summary":
            in_summary = True
            continue
        if in_summary and line.startswith("## "):
            break
        if in_summary and line.strip().startswith("-"):
            item = line.strip()
            qa_summary.append(item)
            if ":" in item:
                key, value = item.lstrip("- ").split(":", 1)
                summary_counts[key.strip()] = value.strip()

    for line in lines:
        match = re.match(r"^### SEG \d+ \[warning\] ([a-z0-9_\-]+)", line.strip())
        if match:
            warning_types[match.group(1)] += 1
    return qa_summary, summary_counts, warning_types


def write_run_summary(
    work_dir: Path,
    run_dir: Path,
    media: Path,
    language: str,
    domain_name: str,
    outputs_dir: Path,
    output_base: str,
    elapsed: float,
    orchestrator_model: str = "current orchestrating AI (not recorded)",
    translation_model: str | None = None,
) -> None:
    aligned_path = work_dir / "aligned_segments.json"
    report_path = work_dir / "final_qa_report.md"
    transcript_path = run_dir / "transcript" / "transcript_words.json"
    timings_path = work_dir / "step_timings.json"
    helper_meta_path = work_dir / "segment_generation_meta.json"

    segment_count = "unknown"
    if aligned_path.exists():
        payload = read_optional_json(aligned_path)
        if isinstance(payload, dict):
            segment_count = str(len(payload.get("segments", [])))

    transcript = read_optional_json(transcript_path)
    if not isinstance(transcript, dict):
        transcript = {}
    asr_provider = str(transcript.get("provider") or "aliyun-fun-asr")
    asr_model = str(transcript.get("model") or "unknown")
    media_duration = transcript.get("duration")

    word_count = count_word_table(work_dir)
    length_class, length_detail = content_length_class(word_count)

    helper_meta = read_optional_json(helper_meta_path)
    if isinstance(helper_meta, dict):
        translation_path = "helper_dashscope"
        effective_translation_model = str(helper_meta.get("model") or translation_model or "unknown")
        helper_detail = f"fallback={helper_meta.get('fallback_model', 'none')}; concurrency={helper_meta.get('concurrency', 'unknown')}; batches cached via helper"
        source_reference = str(helper_meta.get("source_subtitle") or "none")
        reference_corrected_chunks = str(helper_meta.get("reference_corrected_chunks") or 0)
    else:
        translation_path = "main_orchestrator"
        effective_translation_model = translation_model or orchestrator_model
        helper_detail = "not used"
        source_reference = "none"
        reference_corrected_chunks = "0"

    timings = read_optional_json(timings_path)
    timing_lines: list[str] = []
    if isinstance(timings, dict) and isinstance(timings.get("steps"), dict):
        for step, item in timings["steps"].items():
            if isinstance(item, dict):
                detail = item.get("detail", "")
                suffix = f"; {detail}" if detail else ""
                timing_lines.append(f"- {step}: {float(item.get('seconds', 0.0)):.1f}s ({float(item.get('minutes', 0.0)):.1f} min){suffix}")
    if not timing_lines:
        timing_lines = ["- Step timings unavailable for this run invocation."]

    qa_summary, summary_counts, warning_types = qa_summary_from_report(report_path)
    warning_total = summary_counts.get("Warnings", "unknown")
    blocker_total = summary_counts.get("Blockers", "unknown")
    top_warning_lines = [f"- {name}: {count}" for name, count in warning_types.most_common(8)]
    if not top_warning_lines:
        top_warning_lines = ["- No QA warning categories detected."]

    duration_text = "unknown"
    if isinstance(media_duration, (int, float)):
        duration_text = f"{float(media_duration) / 60:.1f} min"

    lines = [
        "# Run Summary",
        "",
        f"- Generated: {dt.datetime.now().isoformat(timespec='seconds')}",
        f"- Media: {media}",
        f"- Media duration: {duration_text}",
        f"- Source language: {language}",
        "- Target language: Chinese",
        f"- Domain: {domain_name}",
        f"- Run dir: {run_dir}",
        f"- Segments: {segment_count}",
        f"- ASR word count: {word_count if word_count is not None else 'unknown'}",
        f"- Content length class: {length_class} ({length_detail})",
        f"- Total elapsed this invocation: {elapsed:.1f}s ({elapsed / 60:.1f} min)",
        "",
        "## Models",
        "",
        f"- ASR provider: {asr_provider}",
        f"- ASR model: {asr_model}",
        f"- Orchestrator model: {orchestrator_model}",
        f"- Segment translation path: {translation_path}",
        f"- Segment translation model: {effective_translation_model}",
        f"- Helper detail: {helper_detail}",
        f"- Source subtitle reference: {source_reference}",
        f"- Reference-corrected chunks: {reference_corrected_chunks}",
        "",
        "## Step Timings",
        "",
    ]
    lines.extend(timing_lines)
    lines.extend(
        [
            "",
            "## Outputs",
            "",
            f"- ASS: {outputs_dir / (output_base + '.ass')}",
            f"- SRT: {outputs_dir / (output_base + '.srt')}",
            "",
            "## QA Summary",
            "",
        ]
    )
    lines.extend(qa_summary or ["- QA summary unavailable"])
    lines.extend(
        [
            "",
            "## Warning Breakdown",
            "",
            f"- Blockers: {blocker_total}",
            f"- Warnings: {warning_total}",
        ]
    )
    lines.extend(top_warning_lines)
    summary_text = "\n".join(lines).rstrip() + "\n"
    print("\n" + summary_text, flush=True)


def run_deterministic_qa(
    work_dir: Path,
    domain_name: str,
    glossary: Path,
    term_rules: Path,
    disable_domain_term_checks: bool,
) -> None:
    segments = work_dir / "segments.txt"
    aligned = work_dir / "aligned_segments.json"
    word_table = work_dir / "word_table.json"

    def align() -> None:
        run_step(
            [
                sys.executable,
                "scripts/align_segments.py",
                str(word_table),
                str(segments),
                "--out",
                str(aligned),
            ]
        )

    def final_qa() -> int:
        final_qa_cmd = [
            sys.executable,
            "scripts/final_qa.py",
            str(aligned),
            str(segments),
            "--domain-name",
            domain_name,
            "--glossary",
            str(glossary),
            "--qa-rules",
            str(term_rules),
        ]
        if disable_domain_term_checks:
            final_qa_cmd.append("--disable-domain-term-checks")
        return run_step_status(final_qa_cmd)

    def auto_fix() -> bool:
        """Run the deterministic merger; returns True when segments.txt changed."""
        before = segments.read_text(encoding="utf-8")
        run_step([sys.executable, "scripts/auto_fix_segments.py", str(word_table), str(segments)])
        if segments.read_text(encoding="utf-8") == before:
            return False
        run_step([sys.executable, "scripts/validate_segments.py", str(word_table), str(segments)])
        align()
        return True

    run_step([sys.executable, "scripts/repair_segments_terms.py", str(segments), "--rules", str(term_rules)])
    run_step(
        [
            sys.executable,
            "scripts/validate_segments.py",
            str(word_table),
            str(segments),
            "--auto-repair",
        ]
    )
    align()

    # Deterministic auto-fix: merge mechanically-fixable cues (fillers, flash
    # subtitles, continuation fragments, hanging boundaries), then re-run QA.
    auto_fix()
    qa_status = final_qa()
    if qa_status != 0 and auto_fix():
        qa_status = final_qa()

    if qa_status != 0:
        print("", flush=True)
        print("Final QA found blockers that need AI review; subtitles were NOT exported.", flush=True)
        print(f"- Report: {work_dir / 'final_qa_report.md'}", flush=True)
        print(f"- AI repair prompt: {work_dir / 'final_qa_prompt.txt'}", flush=True)
        print(
            "AI runner: use final_qa_prompt.txt to revise the affected files under "
            "global_review/semantic/reviewed/, refresh their receipt hashes, then rerun this command.",
            flush=True,
        )
        print("Ask the user only if the same blocker remains after two AI repair attempts or the fix needs domain judgment.", flush=True)
        raise SystemExit(1)

def export_subtitle_files(
    work_dir: Path,
    subtitles_dir: Path,
    outputs_dir: Path,
    output_base: str,
    source_first: bool,
) -> None:
    aligned = work_dir / "aligned_segments.json"
    export_cmd = [
        sys.executable,
        "scripts/export_subtitles.py",
        str(aligned),
        "--out-dir",
        str(subtitles_dir),
        "--basename",
        output_base,
    ]
    if source_first:
        export_cmd.append("--source-first")
    run_step(export_cmd)

    outputs_dir.mkdir(parents=True, exist_ok=True)
    for ext in ("srt", "ass"):
        source = subtitles_dir / f"{output_base}.{ext}"
        target = outputs_dir / f"{output_base}.{ext}"
        shutil.copyfile(source, target)
        print(f"Wrote output: {target}", flush=True)


def semantic_review_gate(work_dir: Path) -> bool:
    segments = work_dir / "segments.txt"
    initial_segments = work_dir / "segments.initial.txt"
    semantic_dir = work_dir / "global_review" / "semantic"
    if not initial_segments.exists():
        shutil.copyfile(segments, initial_segments)
    run_step(
        [
            sys.executable,
            "scripts/global_review.py",
            "prepare-semantic",
            "--segments",
            str(initial_segments),
            "--word-table",
            str(work_dir / "word_table.json"),
            "--out-dir",
            str(semantic_dir),
        ]
    )
    receipt = semantic_dir / "semantic-review-receipt.json"
    if not receipt.exists():
        print("", flush=True)
        print("Mandatory whole-document semantic review is required before deterministic QA.", flush=True)
        print(f"- Follow the procedure in: {semantic_dir / 'WORKFLOW.md'}", flush=True)
        print(f"- Read every section listed in: {semantic_dir / 'manifest.json'}", flush=True)
        print(f"- Build global context from: {semantic_dir / 'semantic-review-receipt.template.json'}", flush=True)
        print(f"- Write reviewed target sections under: {semantic_dir / 'reviewed'}", flush=True)
        print(f"- Save the completed receipt as: {receipt}", flush=True)
        print("- Rerun with the same --run-id after the orchestrator has reviewed every section.", flush=True)
        return False
    reviewed_segments = semantic_dir / "segments.global-reviewed.txt"
    status = run_step_status(
        [
            sys.executable,
            "scripts/global_review.py",
            "validate-semantic",
            "--manifest",
            str(semantic_dir / "manifest.json"),
            "--receipt",
            str(receipt),
            "--reviewed-dir",
            str(semantic_dir / "reviewed"),
            "--out",
            str(reviewed_segments),
        ]
    )
    if status != 0:
        print("Semantic review validation failed; no subtitles will be exported.", flush=True)
        return False
    shutil.copyfile(reviewed_segments, segments)
    return True


def final_qc_gate(work_dir: Path) -> bool:
    qc_dir = work_dir / "global_review" / "final-qc"
    global_context = work_dir / "global_review" / "semantic" / "global-context.json"
    run_step(
        [
            sys.executable,
            "scripts/global_review.py",
            "prepare-qc",
            "--segments",
            str(work_dir / "segments.txt"),
            "--qa-report",
            str(work_dir / "final_qa_report.md"),
            "--global-context",
            str(global_context),
            "--out-dir",
            str(qc_dir),
        ]
    )
    receipt = qc_dir / "final-qc-receipt.json"
    if not receipt.exists():
        print("", flush=True)
        print("Mandatory whole-document final consistency QC is required before export.", flush=True)
        print(f"- Follow the procedure in: {qc_dir / 'WORKFLOW.md'}", flush=True)
        print(f"- Read the global context: {global_context}", flush=True)
        print(f"- Read the deterministic QA report: {work_dir / 'final_qa_report.md'}", flush=True)
        print(f"- Read every section listed in: {qc_dir / 'manifest.json'}", flush=True)
        print(f"- Complete: {qc_dir / 'final-qc-receipt.template.json'}", flush=True)
        print(f"- Save the completed receipt as: {receipt}", flush=True)
        print("- If changes are needed, revise semantic review outputs and rerun from that gate.", flush=True)
        return False
    status = run_step_status(
        [
            sys.executable,
            "scripts/global_review.py",
            "validate-qc",
            "--manifest",
            str(qc_dir / "manifest.json"),
            "--receipt",
            str(receipt),
        ]
    )
    if status != 0:
        print("Final whole-document QC validation failed; no subtitles will be exported.", flush=True)
        return False
    return True



def main() -> int:
    args = parse_args()
    started_at = time.monotonic()
    media = args.media.expanduser().resolve()
    if not media.exists():
        print(f"Input media not found: {media}", file=sys.stderr)
        return 2
    if not media.is_file() or media.suffix.lower() not in VIDEO_SUFFIXES:
        print(
            "video-translate accepts video files only; direct audio input is not supported. "
            f"Received: {media}",
            file=sys.stderr,
        )
        return 2
    if not args.confirm_external_processing:
        print(
            "Refusing external processing without --confirm-external-processing. "
            "This workflow uploads the selected audio to OkFile and sends audio/text to Alibaba services.",
            file=sys.stderr,
        )
        return 2

    run_id = args.run_id or slugify(media.stem)
    outputs_dir = args.outputs_dir or default_outputs_dir()
    if not outputs_dir.is_absolute():
        outputs_dir = PROJECT_ROOT / outputs_dir

    runs_dir = args.runs_dir or (outputs_dir / ".work")
    if not runs_dir.is_absolute():
        runs_dir = PROJECT_ROOT / runs_dir

    run_dir = runs_dir / run_id
    transcript_dir = run_dir / "transcript"
    work_dir = run_dir / "work"
    subtitles_dir = run_dir / "subtitles"
    work_dir.mkdir(parents=True, exist_ok=True)
    asr_media = resolve_asr_media(media)
    source_subtitle = resolve_source_subtitle(media, args.source_subtitle)
    record_step_status(
        work_dir,
        "start",
        "running",
        f"media={media}; asr_media={asr_media}; source_subtitle={source_subtitle}; language={args.language}",
    )
    output_tag = args.subtitle_tag or default_subtitle_tag(args.language)
    # Strip stray whitespace from the video name so outputs never contain
    # names like "Example .zh-en.ass".
    output_base = f"{media.stem.strip()}.{output_tag}"

    print(f"Run: {run_id}", flush=True)
    print(f"Media: {media}", flush=True)
    if asr_media != media:
        print(f"Reusing downloader-provided audio for ASR: {asr_media}", flush=True)
    if source_subtitle:
        print(f"Using source subtitle as ASR correction reference: {source_subtitle}", flush=True)
    print(f"Run dir: {run_dir}", flush=True)
    print(f"Outputs: {outputs_dir}", flush=True)
    print_run_expectation(media)

    if not args.skip_env_check:
        record_step_status(work_dir, "environment", "running")
        step_started = time.monotonic()
        run_step([sys.executable, "scripts/check_env.py"])
        record_step_timing(work_dir, "environment", time.monotonic() - step_started)
        record_step_status(work_dir, "environment", "done")

    record_step_status(work_dir, "transcription", "running")
    step_started = time.monotonic()
    ensure_transcript(asr_media, transcript_dir, args.language, args.confirm_external_processing)
    record_step_timing(work_dir, "transcription", time.monotonic() - step_started, f"ASR language={args.language}")
    record_step_status(work_dir, "transcription", "done")

    record_step_status(work_dir, "word_stream", "running")
    step_started = time.monotonic()
    ensure_work_files(transcript_dir, work_dir)
    record_step_timing(work_dir, "word_stream", time.monotonic() - step_started)
    record_step_status(work_dir, "word_stream", "done")
    print_segment_generation_policy(work_dir)

    record_step_status(work_dir, "prompt", "running")
    step_started = time.monotonic()
    ensure_prompt(work_dir, args.domain_name, args.glossary)
    record_step_timing(work_dir, "prompt", time.monotonic() - step_started)
    record_step_status(work_dir, "prompt", "done")

    record_step_status(work_dir, "ai_segments", "running", "fixed qwen-mt-plus helper")
    step_started = time.monotonic()
    maybe_copy_segments(args.segments, work_dir / "segments.txt")
    if not args.segments:
        ensure_ai_segments(work_dir, transcript_dir, args.language, args.domain_name, source_subtitle)
    record_step_timing(
        work_dir,
        "ai_segments",
        time.monotonic() - step_started,
        "copied provided segments" if args.segments else "generated with fixed qwen-mt-plus helper",
    )
    record_step_status(work_dir, "ai_segments", "done", "segments.txt ready")

    record_step_status(work_dir, "semantic_review", "running", "mandatory whole-document orchestrator review")
    step_started = time.monotonic()
    if not semantic_review_gate(work_dir):
        record_step_timing(work_dir, "semantic_review", time.monotonic() - step_started, "waiting for orchestrator review")
        record_step_status(work_dir, "semantic_review", "waiting", "complete all semantic review sections and receipt")
        return 3
    record_step_timing(work_dir, "semantic_review", time.monotonic() - step_started, "validated full-document semantic review")
    record_step_status(work_dir, "semantic_review", "done")

    record_step_status(work_dir, "deterministic_qa", "running")
    step_started = time.monotonic()
    run_deterministic_qa(
        work_dir,
        args.domain_name,
        args.glossary,
        args.term_rules,
        args.disable_domain_term_checks,
    )
    record_step_timing(work_dir, "deterministic_qa", time.monotonic() - step_started, "term repair, validation, alignment, auto-fix, QA")
    record_step_status(work_dir, "deterministic_qa", "done")

    record_step_status(work_dir, "global_qc", "running", "mandatory whole-document consistency QC")
    step_started = time.monotonic()
    if not final_qc_gate(work_dir):
        record_step_timing(work_dir, "global_qc", time.monotonic() - step_started, "waiting for orchestrator QC")
        record_step_status(work_dir, "global_qc", "waiting", "complete final QC receipt")
        return 4
    record_step_timing(work_dir, "global_qc", time.monotonic() - step_started, "validated full-document final QC")
    record_step_status(work_dir, "global_qc", "done")

    record_step_status(work_dir, "export", "running")
    step_started = time.monotonic()
    export_subtitle_files(work_dir, subtitles_dir, outputs_dir, output_base, args.source_first)
    record_step_timing(work_dir, "export", time.monotonic() - step_started, "ASS/SRT export after both global gates")
    elapsed = time.monotonic() - started_at
    orchestrator_model = model_name_from_env(args.orchestrator_model)
    translation_model = args.translation_model or "qwen-mt-plus"
    write_run_summary(
        work_dir,
        run_dir,
        media,
        args.language,
        args.domain_name,
        outputs_dir,
        output_base,
        elapsed,
        orchestrator_model,
        translation_model,
    )
    record_step_status(work_dir, "export", "done", f"outputs={outputs_dir}")
    if not args.keep_workflow_inputs:
        removed_inputs = cleanup_workflow_inputs(media, [asr_media, source_subtitle])
        if removed_inputs:
            print("Removed temporary combined-workflow inputs:", flush=True)
            for removed in removed_inputs:
                print(f"- {removed}", flush=True)
            record_step_status(work_dir, "input_cleanup", "done", f"removed={len(removed_inputs)}")
    print(f"Done in {elapsed:.1f}s ({elapsed / 60:.1f} min)", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print_failure_guidance(exc)
        raise SystemExit(1)
