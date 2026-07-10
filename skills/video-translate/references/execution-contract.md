# Video Translation Execution Contract

Read this file in full before running, resuming, repairing, or changing a production subtitle job. `SKILL.md` is the short entrypoint; this file is the detailed execution contract.

Author / workflow owner: `AI落地第四声`. Author information is for display and source identification only.

## Operating Contract

Use this skill for local media files only. The fixed production stack is:

1. Extract compact audio locally with `ffmpeg`.
2. Upload audio to OkFile and get a public URL.
3. Submit the URL to Alibaba Fun-ASR.
4. Use Fun-ASR word timestamps as the alignment source of truth.
5. Create `segments.txt` automatically with the fixed Alibaba `qwen-mt-plus` helper.
6. Repair terms, validate `SRC_RAW` (with automatic recovery of lightly rewritten lines), align word timestamps, auto-merge mechanically-fixable cues, run QA, and export SRT/ASS.

Do not switch ASR providers, use local Whisper, or add backup paths unless the user explicitly asks.


## Fixed Model Policy

Do not ask ordinary users to choose among many models. The production stack is fixed because it has been tested on real subtitle jobs and is more reliable than ad-hoc model switching.

- ASR: Alibaba Bailian / DashScope `Fun-ASR`. It is required because the workflow depends on long-recorded-audio ASR and word-level timestamps.
- Segment translation/generation: Alibaba Bailian `qwen-mt-plus`, called by `scripts/generate_segments_with_dashscope.py`. This is now the normal production path for creating `segments.txt`, with cache/resume support. Production concurrency is fixed to serial mode (`--concurrency 1`) because qwen-mt-plus is more stable and avoids rate-limit fallback/chaos; quality and reliability are prioritized over maximum speed. The qwen-mt path uses the workspace-specific Alibaba endpoint from `ALIYUN_WORKSPACE_ID` / `ALIYUN_REGION` and sends no `system` role because Qwen-MT accepts only `user`/`assistant` roles.
- Orchestrator: if running in WorkBuddy, use DeepSeek V4 Pro. If running in Codex/Cursor or a coding-agent environment, recommend GPT 5.5-class models. The orchestrator runs tools, keeps long tasks alive, performs timestamp alignment, QA repair, subtitle export, and returns the final chat summary.

Do not switch ASR providers, use local Whisper, or add backup model paths unless the user explicitly asks for that engineering change and accepts revalidation. Groq Whisper or other providers must prove word-level timestamps before production use.

## Required Setup

Run commands from the skill folder, or copy the skill folder into the working project and run there.

User-side accounts and secrets:

- OkFile account: register at `https://www.okfile.com/`, then create or copy the API key from `https://www.okfile.com/en/account/api-keys`.
- Alibaba Cloud / Model Studio account: sign in at `https://bailian.console.aliyun.com/`, create a DashScope API key, and add a small balance such as 2-10 CNY before batch use.
- Required values: `DASHSCOPE_API_KEY`, `ALIYUN_WORKSPACE_ID`, and `OKFILE_TOKEN`.
- Required media: the video or audio file must exist locally and be readable by the runner.

Create a local `.env` file in the skill/project working folder. Do not package a standalone environment-template file; SkillHub rejects packages containing standalone environment template files.

Use this template content:

```text
DASHSCOPE_API_KEY=...
ALIYUN_WORKSPACE_ID=...
ALIYUN_REGION=cn-beijing
ALIYUN_ASR_MODEL=fun-asr
ALIYUN_ASR_VOCABULARY_ID=
OKFILE_TOKEN=...

```

Never print or reveal real API keys.

Local requirements:

- Python 3.9+
- `ffmpeg`
- network access to OkFile and Alibaba Model Studio / DashScope
- enough local disk space for temporary audio, transcripts, prompts, and subtitle outputs

On a new device or first run, always check the environment before processing media:

```bash
python scripts/check_env.py
```

If the check fails, fix the environment before running transcription. For missing tools such as `ffmpeg`, give the platform-specific install command or request user approval before installing. Do not silently install system tools. On later runs, skip repeated environment setup only when the same environment already passed the check.

## Use Case Guidance

Use this workflow confidently for courses, training videos, lectures, finance/trading explanations, interviews, podcasts, market reviews, software tutorials, PPT walkthroughs, chart explanations, and batch subtitle production after a sample check.

For screen recordings, PPT/slides, code, charts, or software UI, decide whether visible information materially affects translation. Enable screen context only when it does.

For non-finance domains, keep the pipeline but ask for or maintain a domain glossary and term rules. For non-Chinese target languages, explain that the architecture can be extended but needs target-specific prompt/glossary/QA/export rules before production use.

## Before Running

First use message after environment check, in Chinese:

```text
这套工作流会先在本地准备所选视频的音频，通过 OkFile 生成临时音频链接，再用阿里 Fun-ASR 做词级转写；随后固定调用阿里 qwen-mt-plus 生成分段翻译，最后由当前 AI agent 做时间轴匹配、术语修复、质检和 ASS/SRT 导出。音频会上传至 OkFile，临时链接会发送给阿里 Fun-ASR，字幕文本会发送给阿里 qwen-mt-plus；只有在你明确同意后才会开始外发。当前固定模型组合是多轮视频测试后效果和性价比最稳的方案：转写用 Fun-ASR，分段翻译用 qwen-mt-plus；WorkBuddy 编排建议用 DeepSeek V4 Pro，Codex/Cursor 编排建议用 GPT 5.5 级模型。请准备 DASHSCOPE_API_KEY、ALIYUN_WORKSPACE_ID、OKFILE_TOKEN 并写入 .env，准备好后把本地视频路径发来即可。详细说明可看：视频翻译工作流说明书.md。
```

Before starting each user-provided video, confirm only these points unless already clear:

1. Source language: default English (`--language en`). Common supported hints: French (`fr`), Spanish (`es`), Italian (`it`). If uncertain, infer and state the assumption.
2. Target language: default Chinese. Current glossary, QA rules, subtitle style, and hotword policy are optimized for Chinese output. Other targets require target-specific rules before production quality is claimed.
3. Screen context: ask whether the video contains dense or important visible text, PPT/slides, charts, software UI, code, signs, or meaningful images not fully spoken aloud. Keep it off by default; enabling it may increase time and cost.
4. Subtitle output directory: default to the project-level `outputs/` directory. Ask the user to confirm this default; if they want a different location, ask for the absolute or project-relative path and pass it with `--outputs-dir "<path>"`.
5. External-processing consent: before any command runs, state that the selected audio is uploaded only to `https://www.okfile.com`; its temporary URL is sent to Alibaba Fun-ASR; and subtitle text is sent to Alibaba qwen-mt-plus. Proceed only after an explicit affirmative answer.

Do not ask the user to select ASR/helper/orchestration models during ordinary production runs.

## Capability Boundaries

- Recorded local video/audio files only; no real-time subtitles or live interpretation.
- Exports ASS/SRT subtitle files; does not hard-code subtitles into the video.
- Default target language is Chinese, and the current prompts, QA rules, glossary, subtitle style, and hotword assumptions are Chinese-output oriented. Other target languages require target-specific extensions before production use.
- Low-quality audio, heavy accents, overlapping speakers, and noisy recordings can significantly reduce ASR accuracy.
- Optional screen context is for visual-text assistance only and stays off by default.
- The workflow reads only the selected media, an optional same-basename audio file, and its local `.env`; it writes only to the confirmed output folder and its `.work/<run-id>` subfolder.
- The skill never searches for credentials, scans unrelated files, installs software, uses `sudo`, or accepts arbitrary upload endpoints. Network processing is rejected unless the caller supplies `--confirm-external-processing`.

## Troubleshooting Contract

When a run fails, identify the failure category, quote the code if present, and give a concrete next step. Do not hand the user a raw traceback. Use `workflow_status.json` and `python scripts/check_env.py --json` as the lightweight diagnostic surface.

- `VTZ-E001` environment or secret configuration: run `python scripts/check_env.py`; install missing Python/ffmpeg or fill `.env`.
- `VTZ-E002` ffmpeg: install ffmpeg and rerun `python scripts/check_env.py`.
- `VTZ-E003` OkFile: check `OKFILE_TOKEN`, network access, quota, and cached URL age; rerun the same command.
- `VTZ-E004` Alibaba/Fun-ASR: check `DASHSCOPE_API_KEY`, `ALIYUN_WORKSPACE_ID`, `ALIYUN_REGION`, account balance, and service status; rerun the same command.
- `VTZ-E005` AI segment contract or QA blocker: the AI runner must first repair `segments.txt` with `final_qa_prompt.txt` / `final_qa_report.md`, then rerun. Ask the user only if the same blocker remains after two AI repair attempts or the fix needs domain judgment.

Use the same `--run-id` when retrying so completed stages can be reused.

## Long Run Heartbeats

Before starting any video longer than about 10 minutes, tell the user:

- video duration if detectable;
- rough first-run estimate, with a clear warning that upload speed, Alibaba queueing, AI model speed, and optional screen context affect it;
- the status heartbeat rhythm: report every 10 minutes until completion or until the workflow pauses for `segments.txt`.

During long runs, do not go silent, do not end the agent turn while a subprocess/background task is still running, and do not make a vague “wait for notification” promise. On WorkBuddy-like platforms, task notifications may not wake the agent without another user message, so keep the subprocess in foreground or loop-poll task output/status until it finishes, pauses for `segments.txt`, or fails. Every 10 minutes, summarize:

- current stage (`environment`, `transcription`, `word_stream`, `prompt`, `ai_segments`, `export`, or QA repair);
- what has already completed;
- whether cached artifacts are being reused;
- rough remaining work if enough information is available.

After each completed run, use the printed final summary elapsed time and media duration to improve future estimates for the same environment/model. Do not claim exact timing; give ranges. On platforms where one blocking call may return only a running snapshot, poll repeatedly in the same turn until the task is actually done.


## Main Workflow

User-facing trigger is natural language: the user can paste a local media path and ask the AI to translate subtitles with this skill. The command below is the AI runner implementation detail; users should not need to memorize it.

Run:

```bash
python scripts/video_to_subtitles.py "/absolute/path/to/video.mp4" --language en --confirm-external-processing
```

If the user confirmed a custom subtitle export directory, add:

```bash
--outputs-dir "/absolute/or/project-relative/output/folder"
```

Optional screen context: if the user confirms important visible text, charts, slides, UI labels, code, signs, or screen-only terms, read `references/screen_context.md`. Use `ffmpeg` for local screenshot/contact-sheet generation. The same multimodal AI should inspect screenshots and create `runs/<run-id>/work/screen_context.txt` before `prompt.txt` is generated or regenerated. Do not use local OCR or bind this step to a specific model, platform, or operating system. Keep it off by default. Use 6-12 screenshots normally, 16 for 30-60 minute videos, and never exceed 20 screenshots without asking the user. If `screen_context.txt` exists, the workflow injects it into `prompt.txt` and passes it to the segment helper.

Normal run lifecycle:

1. The wrapper checks environment, transcribes with Fun-ASR, extracts word stream, and writes `prompt.txt` for audit/repair context.
2. If `segments.txt` does not already exist or was not supplied with `--segments`, the wrapper automatically calls `scripts/generate_segments_with_dashscope.py --model auto`, which resolves to fixed `qwen-mt-plus`.
3. The wrapper repairs terms, validates `SRC_RAW`, aligns timestamps, runs automatic merge/fix, final QA, and ASS/SRT export.
4. If QA blocks export, the AI runner repairs `segments.txt` using `final_qa_prompt.txt` and `final_qa_report.md`, then reruns. Ask the user only after two failed AI repair attempts or when domain judgment is required.
5. After successful export, return the completion summary in chat.

## `segments.txt` Format

Every segment must be:

```text
[SEG 0001]
SRC_RAW: exact normalized words copied from the input word stream
SRC_DISPLAY: readable source-language sentence with punctuation and repaired split words
ZH: 自然、地道、简洁的中文翻译。
[/SEG]
```

Hard rules:

- `SRC_RAW` is the timestamp matching contract. Do not translate it.
- Copy `SRC_RAW` exactly from the normalized word stream: no punctuation, no inserted words, no deleted words.
- The full set of `SRC_RAW` spans must cover the entire word stream exactly once and in order.
- `SRC_DISPLAY` and `ZH` must describe only the current `SRC_RAW` span. Do not borrow words or meaning from adjacent segments just to complete a sentence.
- Repair ASR split words and obvious ASR mishearings only in `SRC_DISPLAY` and `ZH`. Keep `SRC_RAW` unchanged. Example: if ASR says `from tony` but the numeric/year context says `from twenty, starting from 2015`, display and translate the intended numeric phrase, not a person named Tony.
- For non-English videos, `SRC_DISPLAY` is the readable source-language line.
- Merge tiny oral fillers with adjacent context when they are not meaningful alone. Isolated oral fillers such as `m`, `um`, and `uh` must be merged into neighboring `SRC_RAW` spans and should not export as standalone subtitles.
- Merge dangling continuation fragments with adjacent context. Short spans that start with continuation words such as `of`, `into`, `to`, `with`, or `for` usually complete the previous cue and should not become standalone subtitles.
- Keep the Chinese line natural for the domain, not literal or textbook-like.

## Segmentation Rules

Prefer semantic subtitle rhythm over raw ASR boundaries. Use `asr_segments_reference.txt` as a checklist, not as mandatory boundaries.

Visual guardrail:

- Target rhythm: most cues should feel light, usually 1.8-5.8s and roughly 12-36 Chinese characters.
- Do not merge 2-4 complete short sentences into one heavy subtitle.
- If a cue is over 8s and over 24 source-language words, split it at natural semantic boundaries unless the source is genuinely inseparable.
- If a cue is under 0.8s and has weak information value, merge it with a neighboring cue.

- If the Chinese translation fits within about 3 visual lines, keep the segment unchanged.
- If the Chinese translation exceeds about 3 visual lines, split it.
- Split only after re-understanding the full meaning and choosing a weak semantic boundary.
- Never split mechanically by source-language word count, source-language character count, or equal chunk size.
- Do not split just because the source-language line is long; Chinese is the primary viewing line.

This rule exists because Chinese and source-language word order can differ. Mechanical splits can make the Chinese meaning appear before or after the matching screen action.

## Translation Style

Default domain is finance/trading training videos. Load and follow:

```text
references/trading_glossary.md
references/term_repair_rules.json
```

Use trading-circle Chinese, not stiff textbook Chinese. `first red day` / `the first red day` is `首阴日`. Preserve common trading terms when they are normally used in English, such as `delta`, `footprint`, `imbalance`, `POC`, `value area`, `long`, `short`, and platform/product names.

For another domain, use the same workflow but provide a new glossary and repair rules:

```bash
python scripts/video_to_subtitles.py "/path/to/video.mp4" \
  --language en \
  --confirm-external-processing \
  --domain-name "film subtitles" \
  --glossary references/film_glossary.md \
  --term-rules references/film_term_repair_rules.json \
  --disable-domain-term-checks
```

## QA And Export

After `segments.txt` exists, rerun the main command. The wrapper first runs a deterministic
auto-fix stage before QA:

- `validate_segments.py --auto-repair` restores `SRC_RAW` lines that a model lightly rewrote
  (up to 2 token edits) by copying the exact words back from the original word stream; a
  `.bak` backup is kept.
- `auto_fix_segments.py` merges mechanically-fixable cues: isolated oral fillers, dangling
  continuation fragments, flash subtitles under 0.8s, cues under 0.5s, and hanging
  connective boundaries followed by a short cue. Every merge must keep the merged cue within
  the viewing-rhythm guardrails (at most 8s, 24 source words, 3 wrapped Chinese lines);
  otherwise the issue is left for AI review. `SRC_RAW` spans are only concatenated, never
  rewritten.

If blockers remain after auto-fix, subtitles are NOT exported. The wrapper prints the paths
of `final_qa_report.md` and `final_qa_prompt.txt`; fix `segments.txt` (or apply the AI
repair prompt), then rerun the same command. Fix any blocker before delivery.

Domain QA rules (bad Chinese terms, ASR split-word display patterns) load from the
`qa_bad_zh_terms` / `qa_split_display_patterns` sections of the term rules JSON, so a custom
domain only needs one rules file.

The QA checks and required review items:

- match failures between `SRC_RAW` and the word table
- full word-stream coverage
- bad timing and overlaps
- display/translation scope drift, where `SRC_DISPLAY` or `ZH` appears to borrow content outside the current `SRC_RAW` span
- undertranslated scope drift, where `SRC_RAW` is substantial but `ZH` is only a tiny fragment
- dense long subtitles: over 8s and over 24 source-language words; Chinese visual overflow is checked separately with the 3-line rule
- flash subtitles: under 0.8s with weak information value
- Chinese visual overflow using the same manual wrapping logic as export
- awkward final Chinese wrap tails shorter than 4 visible characters
- fast Chinese reading speed
- ASR split-word leftovers
- when `work/screen_context.txt` is present, review visible terms and screen references against `SRC_DISPLAY` and `ZH`
- known bad trading terms

Warnings and info do not block export mechanically, but production delivery should include one focused polish pass on warnings that may affect meaning, untranslated fragments, ASR mishearing, term quality, awkward rhythm, or visible subtitle quality. Remaining warnings are acceptable only when they are false positives, low-value reading-speed hints, or repeated repair would cost disproportionate time.

Final outputs are copied to:

```text
outputs/<original-video-name>.zh-<source-language>.srt
outputs/<original-video-name>.zh-<source-language>.ass
```

## Completion Response Contract

After a run successfully exports subtitles, do not finish with only file paths or a vague “done”. Return a concise chat message using the printed final summary, `workflow_status.json`, and `final_qa_report.md`. The message must include:

- ASS output path
- SRT output path
- total elapsed time
- per-stage timing when available
- ASR provider/model
- orchestrating model
- segment translation model (`qwen-mt-plus` in production)
- QA blocker count
- QA warning count and the main warning types, if available
- whether any focused human spot-check is recommended

Use this shape:

```text
字幕已完成。

输出文件：
- ASS: ...
- SRT: ...

本次耗时：...
- 环境检查/复用：...
- 转写：...
- AI 分段翻译：...
- 对齐/导出/QA：...

模型：
- ASR：...
- 编排模型：...
- 分段翻译模型：qwen-mt-plus

QA：
- Blockers: ...
- Warnings: ...
- 主要类型：...
- 建议：...
```

ASS is the preferred viewing format:

- one `Dialogue` event per cue
- Chinese on top, source language below
- Chinese font size `42`
- source-language font size `24`
- manual Chinese line breaks for long CJK text: about 36 Chinese-width characters per line, prefer punctuation within a 2-3 character adjustment window, avoid short trailing tails by falling back to an earlier punctuation point when needed, merge a final line shorter than 4 non-space characters back into the previous line, and omit final Chinese soft punctuation (`。` / `，`) in exported subtitle display while preserving `？` / `！`

SRT is plain text and cannot reliably control font size across players.

## Segment Translation Helper

`scripts/generate_segments_with_dashscope.py` is no longer an optional fallback in production. It is the fixed segment generation path and defaults to `qwen-mt-plus` when `--model auto` is used. Always pass `--cache` so interrupted runs resume instead of retranslating completed chunks.

Manual example for diagnostics or controlled re-generation:

```bash
python scripts/generate_segments_with_dashscope.py \
  runs/<run-id>/transcript/transcript_words.json \
  --out runs/<run-id>/work/segments.txt \
  --cache runs/<run-id>/work/dashscope_translation_cache.json \
  --model auto \
  --source-language-name Italian \
  --domain-name "finance/trading training videos"
```

Always run validation and final QA afterward.

## Re-export Existing Runs

If ASR and `segments.txt` already exist and the task is only to apply updated QA/export/style rules, use:

```bash
python scripts/finalize_run.py runs/<run-id> \
  --output-base "<original-video-name>.zh-en" \
  --language en
```

This does not call OkFile or Fun-ASR. It runs term repair, validation, alignment, final QA, SRT/ASS export, and prints the final summary to the console/chat.

## Cleanup Completed Runs

After the user accepts the final subtitles and no V2 edits are needed, clean disposable run files. Always preview first:

```bash
python scripts/clean_run.py runs/<run-id>
```

Delete only after acceptance:

```bash
python scripts/clean_run.py runs/<run-id> --confirm
```

The cleaner removes upload audio copies, screenshot/screen-context scratch files, translation caches, backup fragments, and temporary QA prompts. It keeps the reproducibility core: `transcript_words.json`, `word_table.json`, `word_stream.txt`, `asr_segments_reference.txt`, `screen_context.txt`, `prompt.txt`, `segments.txt`, `aligned_segments.json`, `final_qa_report.md`, and exported subtitles. Do not clean before final QA passes and the user confirms the delivered subtitles are good.
