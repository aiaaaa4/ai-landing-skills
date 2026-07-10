#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from common import normalize_word


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = "auto"
DEFAULT_PREFERRED_HELPER_MODEL = "qwen-mt-plus"
DEFAULT_FALLBACK_MODEL = ""
GENERAL_CHAT_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"  # Not used by qwen-mt-*; qwen-mt uses workspace URL from qwen_mt_chat_url(env).
QWEN_MT_PREFIX = "qwen-mt-"
QWEN_MT_TARGET_LANG = "Chinese"
QWEN_MT_SOURCE_LANG_MAP = {
    "english": "English",
    "en": "English",
    "french": "French",
    "fr": "French",
    "spanish": "Spanish",
    "es": "Spanish",
    "italian": "Italian",
    "it": "Italian",
}


@dataclass
class DisplayToken:
    text: str
    norm: str
    start: int
    end: int
    raw_start: int | None = None
    raw_end: int | None = None


@dataclass
class SegmentChunk:
    key: str
    source_raw: str
    source_display: str


TOKEN_RE = re.compile(r"[0-9]+(?:[:.,][0-9]+)*%?|[A-Za-zÀ-ÖØ-öø-ÿ]+(?:[’'][A-Za-zÀ-ÖØ-öø-ÿ]+)?")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate segments.txt from Fun-ASR transcript using DashScope translation.")
    parser.add_argument("transcript_words", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--cache", type=Path, default=None)
    parser.add_argument("--env", type=Path, default=PROJECT_ROOT / ".env")
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=(
            "DashScope helper model id. Use 'auto' for the fixed production helper model qwen-mt-plus. "
            "Override only for controlled internal tests."
        ),
    )
    parser.add_argument(
        "--fallback-model",
        default=None,
        help="Optional fallback model for controlled tests. Production default is no fallback because helper is fixed to qwen-mt-plus.",
    )
    parser.add_argument("--source-language-name", default="source-language")
    parser.add_argument("--domain-name", default="finance/trading training videos")
    parser.add_argument("--batch-size", type=int, default=40)
    parser.add_argument("--concurrency", type=int, default=1, help="Parallel DashScope translation batches. Production default is 1 because qwen-mt-plus is more stable in serial mode.")
    parser.add_argument("--heartbeat-seconds", type=int, default=60, help="Print progress at least this often while translating batches.")
    parser.add_argument("--screen-context", type=Path, default=None, help="Optional screen context file.")
    parser.add_argument("--max-display-tokens", type=int, default=18)
    parser.add_argument("--max-retries", type=int, default=8, help="Retries per translation request, including rate-limit backoff.")
    parser.add_argument(
        "--qwen-mt-min-interval-seconds",
        type=float,
        default=1.0,
        help="Minimum interval between qwen-mt requests. Keep production runs at 1 second or higher.",
    )
    return parser.parse_args()


def load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def resolve_helper_model(requested: str, env: dict[str, str], fallback_model: str) -> tuple[str, str]:
    requested = (requested or "").strip()
    if requested and requested.lower() != "auto":
        return requested, "--model"
    return DEFAULT_PREFERRED_HELPER_MODEL, "fixed-default"


def token_norm(text: str) -> str:
    return re.sub(r"[^0-9A-Za-zÀ-ÖØ-öø-ÿ]+", "", text).lower()


def display_tokens(text: str) -> list[DisplayToken]:
    return [
        DisplayToken(match.group(0), token_norm(match.group(0)), match.start(), match.end())
        for match in TOKEN_RE.finditer(text)
        if token_norm(match.group(0))
    ]


def align_tokens_to_raw(tokens: list[DisplayToken], raw_words: list[str]) -> bool:
    raw_norms = [token_norm(word) for word in raw_words]
    raw_pos = 0
    for token in tokens:
        combined = ""
        start = raw_pos
        while raw_pos < len(raw_norms) and len(combined) < len(token.norm):
            combined += raw_norms[raw_pos]
            raw_pos += 1
            if combined == token.norm:
                token.raw_start = start
                token.raw_end = raw_pos
                break
        if token.raw_start is None:
            return False
    return True


def token_boundaries(text: str, tokens: list[DisplayToken], max_tokens: int) -> list[tuple[int, int]]:
    if not tokens:
        return []
    boundaries = [0]
    for i in range(len(tokens) - 1):
        gap = text[tokens[i].end : tokens[i + 1].start]
        if re.search(r"[.!?;:]", gap) or ("," in gap and i + 1 - boundaries[-1] >= 8):
            boundaries.append(i + 1)
    boundaries.append(len(tokens))

    pieces: list[tuple[int, int]] = []
    for start, end in zip(boundaries, boundaries[1:]):
        if end <= start:
            continue
        if end - start <= max_tokens:
            pieces.append((start, end))
            continue
        cursor = start
        while cursor < end:
            next_end = min(end, cursor + max_tokens)
            pieces.append((cursor, next_end))
            cursor = next_end

    merged: list[tuple[int, int]] = []
    for start, end in pieces:
        if merged and end - start <= 3:
            prev_start, _prev_end = merged.pop()
            merged.append((prev_start, end))
        else:
            merged.append((start, end))
    return merged


def chunk_segment(asr_index: int, text: str, raw_words: list[str], max_display_tokens: int) -> list[SegmentChunk]:
    tokens = display_tokens(text)
    aligned = align_tokens_to_raw(tokens, raw_words)
    if not tokens or not aligned:
        raw = " ".join(raw_words).strip()
        return [SegmentChunk(f"S{asr_index:04d}_P01", raw, " ".join(text.split()))] if raw else []

    chunks: list[SegmentChunk] = []
    for part_index, (token_start, token_end) in enumerate(token_boundaries(text, tokens, max_display_tokens), start=1):
        first = tokens[token_start]
        last = tokens[token_end - 1]
        if first.raw_start is None or last.raw_end is None:
            continue
        raw = " ".join(raw_words[first.raw_start : last.raw_end]).strip()
        display = text[first.start : last.end].strip(" ,;:")
        if raw and display:
            chunks.append(SegmentChunk(f"S{asr_index:04d}_P{part_index:02d}", raw, display))
    return chunks


def build_chunks(transcript: dict, max_display_tokens: int) -> list[SegmentChunk]:
    chunks: list[SegmentChunk] = []
    for asr_index, segment in enumerate(transcript.get("segments", []), start=1):
        text = " ".join(str(segment.get("text") or "").split())
        raw_words = [
            normalize_word(str(word.get("word") or word.get("text") or ""))
            for word in segment.get("words", [])
        ]
        raw_words = [word for word in raw_words if word]
        chunks.extend(chunk_segment(asr_index, text, raw_words, max_display_tokens))
    return chunks


def extract_json_array(text: str) -> list[dict]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    start = stripped.find("[")
    end = stripped.rfind("]")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON array found in model response.")
    return json.loads(stripped[start : end + 1])


def is_qwen_mt_model(model: str) -> bool:
    return (model or "").strip().lower().startswith(QWEN_MT_PREFIX)


def qwen_mt_chat_url(env: dict[str, str]) -> str:
    workspace_id = (env.get("ALIYUN_WORKSPACE_ID") or "").strip()
    region = (env.get("ALIYUN_REGION") or "cn-beijing").strip() or "cn-beijing"
    if not workspace_id:
        raise RuntimeError("ALIYUN_WORKSPACE_ID is required when using qwen-mt-plus helper.")
    return f"https://{workspace_id}.{region}.maas.aliyuncs.com/compatible-mode/v1/chat/completions"


def qwen_mt_source_lang(source_language_name: str) -> str:
    key = (source_language_name or "").strip().lower()
    return QWEN_MT_SOURCE_LANG_MAP.get(key, "auto")


def retry_delay_seconds(exc: Exception, attempt: int) -> float:
    """Respect a gateway-provided retry window and otherwise back off conservatively."""
    if isinstance(exc, urllib.error.HTTPError):
        retry_after = exc.headers.get("Retry-After") if exc.headers else None
        if retry_after:
            try:
                return max(1.0, float(retry_after))
            except ValueError:
                pass
    return min(120.0, 10.0 * (2 ** (attempt - 1)))


def dashscope_translate(
    api_key: str,
    model: str,
    batch: list[SegmentChunk],
    max_retries: int,
    source_language_name: str,
    domain_name: str,
    screen_context: str = "",
) -> dict[str, str]:
    system = (
        f"You translate {source_language_name} subtitles into natural Mainland Chinese for {domain_name}. "
        "Use professional but colloquial terminology for the domain. For trading videos, keep terms like "
        "footprint, delta, imbalance, book, cash session, POC, value area, long/short when they are common. "
        "If screen context is provided, use it only to repair visible terms, tickers, UI labels, and screen references; "
        "do not add screen text that is not supported by the source subtitle. Return valid JSON only."
    )
    items = [{"id": item.key, "source": item.source_display} for item in batch]
    context_block = ""
    if screen_context.strip():
        context_block = "Screen context for visible terms and scene references:\n" + screen_context.strip() + "\n\n"
    user = (
        f"Translate each {source_language_name} source subtitle into concise Chinese for video subtitles. "
        "Do not explain. Keep the same ids. Return exactly a JSON array like "
        '[{"id":"S0001_P01","zh":"中文"}].\n\n'
        + context_block
        + json.dumps(items, ensure_ascii=False)
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        GENERAL_CHAT_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                data = json.loads(response.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"]
            translated = extract_json_array(content)
            return {str(item["id"]): str(item["zh"]).strip() for item in translated if item.get("id")}
        except (urllib.error.URLError, urllib.error.HTTPError, KeyError, ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < max_retries:
                wait = retry_delay_seconds(exc, attempt)
                print(f"DashScope request failed ({exc}); retrying in {wait:.0f}s ({attempt}/{max_retries})...", flush=True)
                time.sleep(wait)
    raise RuntimeError(f"DashScope translation failed after {max_retries} attempts: {last_error}")


def dashscope_translate_qwen_mt(
    api_key: str,
    env: dict[str, str],
    model: str,
    item: SegmentChunk,
    max_retries: int,
    source_language_name: str,
) -> dict[str, str]:
    # Qwen-MT rejects system messages; keep the request to user/assistant roles only.
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": item.source_display}],
        "translation_options": {
            "source_lang": qwen_mt_source_lang(source_language_name),
            "target_lang": QWEN_MT_TARGET_LANG,
        },
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        qwen_mt_chat_url(env),
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                data = json.loads(response.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"]
            return {item.key: str(content).strip()}
        except (urllib.error.URLError, urllib.error.HTTPError, KeyError, ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < max_retries:
                wait = retry_delay_seconds(exc, attempt)
                print(f"Qwen-MT request failed ({exc}); retrying in {wait:.0f}s ({attempt}/{max_retries})...", flush=True)
                time.sleep(wait)
    raise RuntimeError(f"Qwen-MT translation failed after {max_retries} attempts: {last_error}")


def load_cache(path: Path | None) -> dict[str, str]:
    if not path or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def optional_text(path: Path | None) -> str:
    if not path or not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def save_cache(path: Path | None, translations: dict[str, str]) -> None:
    if not path:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(translations, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def chunk_batches(items: list[SegmentChunk], batch_size: int) -> list[list[SegmentChunk]]:
    return [items[start : start + batch_size] for start in range(0, len(items), batch_size)]


def translate_pending(
    *,
    api_key: str,
    env: dict[str, str],
    model: str,
    fallback_model: str,
    pending: list[SegmentChunk],
    translations: dict[str, str],
    cache: Path | None,
    batch_size: int,
    concurrency: int,
    max_retries: int,
    source_language_name: str,
    domain_name: str,
    screen_context: str,
    heartbeat_seconds: int,
    qwen_mt_min_interval_seconds: float,
) -> dict[str, str]:
    batches = chunk_batches(pending, batch_size)
    total = len(batches)
    if not batches:
        return translations

    concurrency = max(1, min(concurrency, total))
    print(
        f"DashScope segment generation: {len(pending)} pending chunks, {total} batches, "
        f"concurrency={concurrency}, batch_size={batch_size}; qwen-mt-plus production default is serial for rate-limit stability",
        flush=True,
    )

    completed = 0
    started_at = time.monotonic()
    last_heartbeat = started_at
    last_qwen_mt_request_at: float | None = None

    def run_model(used_model: str, batch: list[SegmentChunk]) -> dict[str, str]:
        nonlocal last_qwen_mt_request_at
        if is_qwen_mt_model(used_model):
            result: dict[str, str] = {}
            for item in batch:
                if last_qwen_mt_request_at is not None:
                    remaining = qwen_mt_min_interval_seconds - (time.monotonic() - last_qwen_mt_request_at)
                    if remaining > 0:
                        time.sleep(remaining)
                last_qwen_mt_request_at = time.monotonic()
                result.update(
                    dashscope_translate_qwen_mt(
                        api_key,
                        env,
                        used_model,
                        item,
                        max_retries,
                        source_language_name,
                    )
                )
            return result
        return dashscope_translate(
            api_key,
            used_model,
            batch,
            max_retries,
            source_language_name,
            domain_name,
            screen_context,
        )

    def translate_one(batch_index: int, batch: list[SegmentChunk]) -> tuple[int, dict[str, str]]:
        used_model = model
        try:
            result = run_model(used_model, batch)
        except RuntimeError as exc:
            if fallback_model and fallback_model != used_model:
                print(
                    f"Batch {batch_index} failed with helper model {used_model}; "
                    f"retrying with fallback model {fallback_model}: {exc}",
                    flush=True,
                )
                used_model = fallback_model
                result = run_model(used_model, batch)
            else:
                raise
        missing = [item.key for item in batch if item.key not in result]
        if missing:
            print(
                f"Batch {batch_index} missed {len(missing)} id(s); retrying missing items individually: {missing[:5]}",
                flush=True,
            )
            by_key = {item.key: item for item in batch}
            for key in missing:
                retry_item = by_key[key]
                retry = run_model(used_model, [retry_item])
                if key in retry:
                    result[key] = retry[key]
            missing = [item.key for item in batch if item.key not in result]
        if missing:
            raise RuntimeError(f"Model response missed ids after individual retry: {missing[:5]}")
        return batch_index, result

    if concurrency == 1:
        for batch_index, batch in enumerate(batches, start=1):
            print(f"Translating batch {batch_index}/{total}: {len(batch)} items", flush=True)
            _idx, result = translate_one(batch_index, batch)
            translations.update(result)
            save_cache(cache, translations)
            completed += 1
            now = time.monotonic()
            elapsed = now - started_at
            avg = elapsed / max(completed, 1)
            remaining = max(total - completed, 0) * avg
            print(
                f"Progress: {completed}/{total} batches; elapsed {elapsed / 60:.1f} min; "
                f"estimated remaining {remaining / 60:.1f} min",
                flush=True,
            )
        return translations

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {
            executor.submit(translate_one, batch_index, batch): batch_index
            for batch_index, batch in enumerate(batches, start=1)
        }
        for future in as_completed(futures):
            batch_index, result = future.result()
            translations.update(result)
            save_cache(cache, translations)
            completed += 1
            now = time.monotonic()
            elapsed = now - started_at
            avg = elapsed / max(completed, 1)
            remaining = max(total - completed, 0) * avg
            if now - last_heartbeat >= heartbeat_seconds or completed == total:
                print(
                    f"Progress: {completed}/{total} batches; last completed batch {batch_index}; "
                    f"elapsed {elapsed / 60:.1f} min; estimated remaining {remaining / 60:.1f} min",
                    flush=True,
                )
                last_heartbeat = now
    return translations


def write_segments(path: Path, chunks: list[SegmentChunk], translations: dict[str, str]) -> None:
    lines: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        zh = translations.get(chunk.key, "").strip()
        if not zh:
            zh = "[待翻译]"
        lines.extend(
            [
                f"[SEG {index:04d}]",
                f"SRC_RAW: {chunk.source_raw}",
                f"SRC_DISPLAY: {chunk.source_display}",
                f"ZH: {zh}",
                "[/SEG]",
                "",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    started_at = time.monotonic()
    env = load_env(args.env)
    api_key = env.get("DASHSCOPE_API_KEY")
    if not api_key:
        raise SystemExit("DASHSCOPE_API_KEY is missing.")
    fallback_model = (args.fallback_model or DEFAULT_FALLBACK_MODEL).strip()
    model, model_source = resolve_helper_model(args.model, env, fallback_model)
    if model_source == "fixed-default":
        print(f"Helper model: {model} (fixed production helper).", flush=True)
    else:
        print(f"Helper model: {model} (from {model_source})", flush=True)
    if fallback_model and fallback_model != model:
        print(f"Fallback helper model: {fallback_model}", flush=True)

    transcript = json.loads(args.transcript_words.read_text(encoding="utf-8"))
    chunks = build_chunks(transcript, args.max_display_tokens)
    translations = load_cache(args.cache)
    print(f"Chunks: {len(chunks)}; cached translations: {len(translations)}", flush=True)

    screen_context = optional_text(args.screen_context)
    if screen_context:
        print(f"Screen context: {args.screen_context}", flush=True)

    pending = [chunk for chunk in chunks if chunk.key not in translations]
    translations = translate_pending(
        api_key=api_key,
        env=env,
        model=model,
        fallback_model=fallback_model,
        pending=pending,
        translations=translations,
        cache=args.cache,
        batch_size=args.batch_size,
        concurrency=args.concurrency,
        max_retries=args.max_retries,
        source_language_name=args.source_language_name,
        domain_name=args.domain_name,
        screen_context=screen_context,
        heartbeat_seconds=args.heartbeat_seconds,
        qwen_mt_min_interval_seconds=max(0.0, args.qwen_mt_min_interval_seconds),
    )

    write_segments(args.out, chunks, translations)
    meta = {
        "path": "helper_dashscope",
        "model": model,
        "model_source": model_source,
        "fallback_model": fallback_model,
        "chunks": len(chunks),
        "cache": str(args.cache) if args.cache else "",
        "batch_size": args.batch_size,
        "concurrency": args.concurrency,
        "elapsed_seconds": round(time.monotonic() - started_at, 3),
    }
    (args.out.parent / "segment_generation_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {args.out}", flush=True)
    print(f"Wrote {args.out.parent / 'segment_generation_meta.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
