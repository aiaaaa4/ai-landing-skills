#!/usr/bin/env python3
from __future__ import annotations

import argparse
import time
from pathlib import Path

from video_to_subtitles import (
    DEFAULT_GLOSSARY,
    DEFAULT_TERM_RULES,
    default_outputs_dir,
    model_name_from_env,
    record_step_timing,
    finalize_subtitles,
    write_run_summary,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Finalize an existing run without rerunning ASR or regenerating the AI prompt.")
    parser.add_argument("run_dir", type=Path, help="Existing run directory that contains work/segments.txt and work/word_table.json.")
    parser.add_argument("--media", type=Path, default=None, help="Original media path, used only for the final chat summary.")
    parser.add_argument("--output-base", required=True, help="Output basename, for example 'video.zh-en'.")
    parser.add_argument("--outputs-dir", type=Path, default=None)
    parser.add_argument("--language", default="en")
    parser.add_argument("--domain-name", default="finance/trading training videos")
    parser.add_argument("--glossary", type=Path, default=DEFAULT_GLOSSARY)
    parser.add_argument("--term-rules", type=Path, default=DEFAULT_TERM_RULES)
    parser.add_argument("--disable-domain-term-checks", action="store_true")
    parser.add_argument("--source-first", action="store_true")
    parser.add_argument("--orchestrator-model", default=None, help="Name of the AI model orchestrating this run, for the final chat summary.")
    parser.add_argument("--translation-model", default="qwen-mt-plus", help="Name of the model used for segments.txt. Production default: qwen-mt-plus.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    started_at = time.monotonic()
    run_dir = args.run_dir.expanduser().resolve()
    work_dir = run_dir / "work"
    subtitles_dir = run_dir / "subtitles"
    outputs_dir = args.outputs_dir or default_outputs_dir()
    if not outputs_dir.is_absolute():
        outputs_dir = Path.cwd() / outputs_dir

    if not (work_dir / "segments.txt").exists():
        raise FileNotFoundError(f"Missing {work_dir / 'segments.txt'}")
    if not (work_dir / "word_table.json").exists():
        raise FileNotFoundError(f"Missing {work_dir / 'word_table.json'}")

    step_started = time.monotonic()
    finalize_subtitles(
        work_dir,
        subtitles_dir,
        outputs_dir,
        args.output_base,
        args.source_first,
        args.domain_name,
        args.glossary,
        args.term_rules,
        args.disable_domain_term_checks,
    )
    record_step_timing(work_dir, "export", time.monotonic() - step_started, "finalize existing run")
    elapsed = time.monotonic() - started_at
    media = args.media.expanduser().resolve() if args.media else Path("unknown")
    orchestrator_model = model_name_from_env(args.orchestrator_model)
    translation_model = args.translation_model or "qwen-mt-plus"
    write_run_summary(work_dir, run_dir, media, args.language, args.domain_name, outputs_dir, args.output_base, elapsed, orchestrator_model, translation_model)
    print(f"Done in {elapsed:.1f}s ({elapsed / 60:.1f} min)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
