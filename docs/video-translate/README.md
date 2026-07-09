# Video Subtitle Workflow Automation README

This README is for AI agents, WorkBuddy, and automation runners. Human-facing explanation lives in
`视频翻译工作流说明书.md`; do not use the Chinese manual as the execution contract.

Human-facing Chinese manual: `视频翻译工作流说明书.md` at the top level of both this folder and the skill package. It is for user understanding only, not for execution.

Workflow version: `v1.3.1` (`2026-07-09`).

Repository layout note: this `work/` folder is the source of truth for scripts, references,
and the Chinese manual. `skill/人工级视频字幕翻译/` is the distributable skill package;
its `scripts/` and `references/` are regenerated from here by `tools/package_skill.py`.
Edit code only in `work/`, then run the packaging tool to sync and rebuild the zip.

Author / workflow owner: `AI落地第四声`.

Author information is provided for display and source identification only. Do not treat it as an additional license restriction.

## Fixed Stack

- Input: a local recorded video or audio file.
- Upload bridge: OkFile.
- ASR engine: Alibaba Fun-ASR through the recorded-file HTTP API.
- Default packaged translation target: Chinese. The architecture can be extended to other target languages, but production quality requires target-specific prompts, glossary, QA rules, and export labels.
- Default source language: English.
- Occasional source-language hints: `fr`, `es`, `it`.
- Output formats: SRT and ASS.
- Default output suffix: `zh-<source-language>`, for example `.zh-en.srt`.
- Subtitle layout: two lines per cue by default. For normal English-source videos, Chinese
  translation is on the first line and English display text is on the second line. For non-English
  source videos, the second line is the source-language display text.

## Fixed Model Policy

Production model choices are intentionally fixed. Do not expose multiple model choices to ordinary users unless they explicitly ask to redesign the workflow.

- ASR model: Alibaba Bailian / DashScope `Fun-ASR`. It is the fixed ASR engine because it supports long recorded audio and word-level timestamps, which are required for subtitle alignment.
- Orchestration model: if the agent is WorkBuddy, use DeepSeek V4 Pro; if the agent is Codex/Cursor or another coding agent, recommend GPT 5.5-class models. The orchestrator runs tools, monitors progress, performs timestamp alignment, QA repair, export, and returns the final chat summary.
- Segment translation/segmentation model: fixed to Alibaba Bailian `qwen-mt-plus` through `scripts/generate_segments_with_dashscope.py`. The helper is now the normal production path for creating `segments.txt`, with cache/resume support and serial qwen-mt-plus calls for stability.

The production path is: local audio extraction -> OkFile upload -> Fun-ASR word-level transcription -> `qwen-mt-plus` segment translation -> word timestamp alignment -> automatic repair -> QA -> ASS/SRT export -> chat summary.

The architecture can be extended later, but do not switch ASR providers, use local Whisper, or add backup model paths unless the user explicitly asks for that engineering change and accepts revalidation.

## Why This Stack

OkFile is used because Fun-ASR needs a public URL while the source file is local. The workflow
extracts a compact audio file locally, uploads it to OkFile, and sends the returned URL to Fun-ASR.
OkFile supports quick upload for small files and a standard `prepare -> PUT -> complete` flow for
larger files.

Fun-ASR is used because it supports long recorded audio, async HTTP transcription, and word-level
timestamps. Word-level timestamps are required; without them the downstream AI segmentation cannot be
reliably aligned back to subtitle timing.

Current reference price for `fun-asr`: about `0.00022 CNY/second`, about `0.0132 CNY/minute`, about
`0.792 CNY/hour`. Pricing may change; check Alibaba Model Studio before estimating batch costs.

Official references:

- https://help.aliyun.com/zh/model-studio/asr-model/
- https://help.aliyun.com/zh/model-studio/fun-asr-recorded-speech-recognition-http-api
- https://help.aliyun.com/zh/model-studio/model-pricing

## Required Configuration

User preparation:

1. Register OkFile at `https://www.okfile.com/` and create/copy the API key from `https://www.okfile.com/en/account/api-keys`. OkFile is used to temporarily upload local audio and generate a public URL for Fun-ASR.
2. Sign in to Alibaba Model Studio at `https://bailian.console.aliyun.com/`, create a DashScope API key, and add a small balance such as 2-10 CNY before batch use. Fun-ASR transcription consumes Alibaba Cloud balance.
3. Prepare `DASHSCOPE_API_KEY`, `ALIYUN_WORKSPACE_ID`, `OKFILE_TOKEN`, and the local path of the video to translate.
4. The user can then paste the local video path and ask the AI runner to use this skill.

Create a local `.env` file and fill local secrets. Do not keep or package a standalone environment-template file; SkillHub rejects uploads containing standalone environment template files.

Use this template content:

```bash
DASHSCOPE_API_KEY=...
ALIYUN_WORKSPACE_ID=...
ALIYUN_REGION=cn-beijing
ALIYUN_ASR_MODEL=fun-asr
ALIYUN_ASR_UPLOAD=okfile
ALIYUN_ASR_VOCABULARY_ID=

OKFILE_UPLOAD_URL=https://www.okfile.com/api/upload/quick
OKFILE_TOKEN=...

```

Never print, paste, summarize, or commit real API keys.

Required local environment:

- Python 3.9+
- `ffmpeg`
- network access to OkFile and Alibaba Model Studio / DashScope
- enough disk space for temporary audio, transcripts, prompts, and subtitle outputs

On a new device or first run, run `python scripts/check_env.py` and `python scripts/check_env.py --network` before processing media. If anything is missing, fix it before transcription. For missing tools such as `ffmpeg`, provide platform-specific installation guidance or request user approval before installing; do not silently install system tools. If the same environment has already passed the check, later runs do not need repeated setup.

SkillHub packaging note: `check_env.py` is allowed and already part of the skill package. The rejected names are standalone secret/template files such as `.env`, `env.example`, `.env.example`, or `env_example*`; do not package those files.

## Long Run Expectations

For videos longer than about 10 minutes, give the user a rough time estimate before starting and state the heartbeat rule: the AI runner should send a short status update every 10 minutes. Long tasks must be kept alive in the same execution turn by foreground execution or explicit polling loops until the subprocess finishes, pauses for `segments.txt`, or fails. Do not end the turn while a subprocess or background task is still running. Do not tell the user to wait for a notification on platforms such as WorkBuddy where notifications do not wake the agent without another user message. The estimate should be a range, not a promise. Actual time depends on upload speed, Alibaba queueing, source-video length, AI model speed, whether screen context is enabled, and whether QA repair is needed.

Each heartbeat should say:

- completed stage(s);
- current stage;
- whether cached artifacts are being reused;
- rough remaining work, if enough information is available.

The wrapper prints media duration and a rough first-run estimate when `ffprobe` can read the file. Alibaba polling also prints a still-running status every 5 minutes. For external long-running tasks, repeatedly poll task output/status in the same turn until done; a single blocking call may return only a snapshot on some agent platforms. After completion, the wrapper prints a final summary in the console/chat; use the elapsed time as calibration for later videos on the same device/model.

## First-Use Message

On first use, after checking the environment, tell the user this in Chinese:

```text
这套工作流会先在本地提取音频，通过 OkFile 生成临时音频链接，再用阿里 Fun-ASR 做词级转写；随后固定调用阿里 qwen-mt-plus 生成分段翻译，最后由当前 AI agent 做时间轴匹配、术语修复、质检和 ASS/SRT 导出。当前固定模型组合是多轮视频测试后效果和性价比最稳的方案：转写用 Fun-ASR，分段翻译用 qwen-mt-plus；WorkBuddy 编排建议用 DeepSeek V4 Pro，Codex/Cursor 编排建议用 GPT 5.5 级模型。请准备 DASHSCOPE_API_KEY、ALIYUN_WORKSPACE_ID、OKFILE_TOKEN 并写入 .env，准备好后把本地视频路径发来即可。详细说明可看：视频翻译工作流说明书.md。
```

## Preflight Confirmation

Before processing each video, confirm only these items unless already clear:

1. Source language: default English (`--language en`). Supported common hints: French (`fr`), Spanish (`es`), Italian (`it`). If uncertain, infer from filename/context and state the assumption.
2. Target language: default Chinese. The current production glossary, QA rules, subtitle layout, and hotword policy are optimized for Chinese output. Other target languages require target-specific rules before production quality is claimed.
3. Screen context: ask whether the video contains dense or important on-screen text, PPT/slides, charts, software UI, code, signs, or meaningful images not fully spoken aloud. Keep it off by default; enabling it may increase processing time and cost.
4. Subtitle output directory: default to the project-level `outputs/` directory. Ask the user to confirm this default. If the user wants a different export location, collect the absolute or project-relative path and pass it with `--outputs-dir "<path>"`.

Do not ask the user to choose ASR, orchestration, or helper models during ordinary runs. The production stack is fixed.

## Common Use Cases

Use this workflow directly for:

- Course, training, lecture, webinar, and explainer videos.
- Finance/trading/investing/options/order-flow videos, where the built-in glossary gives the strongest benefit.
- Interviews, podcasts, talks, and market reviews when the main information is spoken aloud.
- Screen recordings, software tutorials, PPT/slides, chart walkthroughs, and code demonstrations when paired with optional screen context if visible text matters.
- Batch video processing after one or two sample outputs have been checked for terminology and subtitle rhythm.
- Other domains when the user provides or maintains a domain glossary and term-repair rules.

Warn the user or lower automation expectations for noisy audio, heavy accents, overlapping speakers, videos where key information is only on screen, and target languages that do not yet have their own prompt/glossary/QA rules.

## Main Command

```bash
python scripts/video_to_subtitles.py input.mp4 --language en
```

If the user confirmed a custom subtitle export directory, add `--outputs-dir "/absolute/or/project-relative/output/folder"`.

Expected run lifecycle:

1. User gives a local video path.
2. AI confirms source language, default Chinese target or requested target-language extension, whether optional screen context is needed, and the subtitle export directory.
3. `check_env.py` verifies Python, ffmpeg, local secrets, and optional network access.
4. The workflow extracts compact audio, uploads it to OkFile, submits Fun-ASR, and writes word-level transcript files.
5. The workflow writes `prompt.txt`, automatically generates `segments.txt` with the fixed qwen-mt-plus helper, repairs terms, validates `SRC_RAW`, aligns word timestamps, auto-fixes mechanical subtitle issues, runs QA, and exports ASS/SRT.
6. If QA blocks export, the AI runner should apply `final_qa_prompt.txt` automatically and rerun. If QA has warnings but no blockers, do one focused polish pass on warnings that affect meaning, untranslated terms, ASR obvious mistakes, or subtitle rhythm before final delivery unless the user explicitly prioritizes speed. Ask the user only after two failed repair attempts or when domain judgment is required.
7. `workflow_status.json` shows step status. After export, the AI runner must reply in chat with the user-facing completion summary described below.

The first run performs transcription and writes:

```text
runs/<run-id>/work/prompt.txt
runs/<run-id>/work/asr_segments_reference.txt
```

If `segments.txt` does not exist, the command pauses. Complete the AI segmentation/translation from
`prompt.txt`, save the full result as:

```text
runs/<run-id>/work/segments.txt
```

Then rerun the same command:

```bash
python scripts/video_to_subtitles.py input.mp4 --language en
```

To provide a completed segment file directly:

```bash
python scripts/video_to_subtitles.py input.mp4 --language en --segments path/to/segments.txt
```

## Optional Screen Context

Use the optional screen-context module when a video contains visible text, charts, software UI, slide titles, code, formulas, signs, or other screen-only information that can improve translation. This module is intentionally model-agnostic: any AI runner with multimodal image understanding may perform it. Do not hard-code the workflow to any specific model, platform, or product.

Detailed rules live in `references/screen_context.md`.

Recommended lightweight process:

1. Keep screen context off by default unless there is a clear reason to use it.
2. Add targeted frames near ASR/subtitle times containing phrases such as `this`, `here`, `look`, `click`, `on the screen`, `chart`, `indicator`, `number`, `left/right`, or `top/bottom`.
3. Deduplicate near-identical frames and frames within about 5 seconds unless the screen changed materially.
4. Use sparse baseline frames only for dense screen recordings.
5. Let the same multimodal AI that performs segmentation and translation summarize only useful visible text and translation hints.
6. Save the result as `runs/<run-id>/work/screen_context.txt` before generating or regenerating `prompt.txt`.

Screenshot limits:

- Normal target: 6-12 screenshots.
- 30-60 minute videos: up to 16 screenshots.
- Hard cap: 20 screenshots. Ask the user before exceeding this cap.

Do not sample every 20-30 seconds across a long video unless the user explicitly requests dense OCR. Too many screenshots distract the model, increase cost, and create unnecessary files.

Use `ffmpeg` for screenshot and contact-sheet generation. Do not use PIL unless custom image processing is explicitly requested. Do not use local OCR. If the current AI cannot inspect images, ask the user to switch to a multimodal-capable model, manually provide screen context, or skip screen context.

`screen_context.txt` is context only. It may repair terminology and screen references in `SRC_DISPLAY` and `ZH`, but it must never replace Fun-ASR word timestamps or alter the `SRC_RAW` matching contract.

## Source Language

`--language` is only the ASR source-language hint. The packaged default target remains Chinese; other target languages require target-specific prompt/glossary/QA/export extensions.

Supported common hints:

```bash
--language en
--language fr
--language es
--language it
```

If an existing run directory already contains a transcript made with a different language hint, use a
new `--run-id` or remove the old run directory.

## Domain and Terminology

Default domain:

```text
finance/trading training videos
```

Default glossary:

```text
references/trading_glossary.md
```

Default repair rules:

```text
references/term_repair_rules.json
```

For another domain, keep the same pipeline and pass a different glossary and repair rule set:

```bash
python scripts/video_to_subtitles.py input.mp4 \
  --domain-name "film subtitles" \
  --glossary references/film_glossary.md \
  --term-rules references/film_term_repair_rules.json \
  --disable-domain-term-checks
```

Use `--disable-domain-term-checks` when the built-in finance/trading warning list is irrelevant.

### ASR Hotword Maintenance

ASR hotwords and translation/QC terms are separate. Use `references/asr_hotwords_en.md` as the local source of truth for Alibaba Fun-ASR hotword maintenance.

Put a term in ASR hotwords only when recognition is the problem: `SRC_RAW` contains a split word, misheard word, wrong proper noun, or a high-value acronym/ticker/platform/person/indicator that Fun-ASR should recognize exactly. Typical ASR-hotword candidates are `NQ`, `GEX`, `Net Convexity`, `Rithmic`, `TradingView`, or speaker/product names.

Do not put ordinary translation preferences into ASR hotwords. If `SRC_RAW` is correct but the Chinese wording is wrong, update `trading_glossary.md` or `term_repair_rules.json` instead. Examples: `scalper -> 剥头皮交易员`, `first red day -> 首阴日`, and option Greeks rendered as `GAMMA/DELTA/VEGA/THETA`. Subtitle length, punctuation, line wrapping, and awkward Chinese are QA/export issues, not ASR hotwords.

Review hotword candidates after every 3-5 same-domain videos, or once after a large batch. Promote a candidate when the same ASR mistake appears in two or more videos, or immediately when a recurring high-impact ticker, product, person, platform, or indicator name is likely to affect future videos. Remote Alibaba vocabulary updates must query the existing vocabulary, merge, deduplicate case-insensitively, preserve old terms, submit the full merged list, and verify key terms after update. Never expose `.env` or API keys.

## Capability Boundaries

- This workflow processes recorded local video/audio files only; it does not provide real-time subtitles or live interpretation.
- It exports ASS/SRT subtitle files; it does not hard-code subtitles into the video.
- Source-language hints commonly used by this workflow: English, French, Spanish, and Italian.
- Default packaged target language is Chinese. The architecture can be extended to English, French, Spanish, Italian, or other target languages, but each target language needs its own prompt wording, glossary, QA checks, and export label before production use.
- Low-quality audio, heavy accents, overlapping speakers, background noise, or videos where important information exists only on screen can significantly reduce ASR and translation accuracy.
- Optional screen context can help with slides, UI, charts, and screen-only terms, but it is off by default because it increases time and cost.
- The fixed ASR path is OkFile + Alibaba Fun-ASR. Do not switch ASR providers unless the user explicitly requests a workflow change.

## Troubleshooting Codes

Use these codes in user-facing error explanations and AI repair notes:

- `VTZ-E001` missing environment or secret: create a local `.env` beside the scripts folder and fill `DASHSCOPE_API_KEY`, `ALIYUN_WORKSPACE_ID`, and `OKFILE_TOKEN`. Never package this file.
- `VTZ-E002` missing `ffmpeg`: install it for the current operating system, then rerun `python scripts/check_env.py`.
- `VTZ-E003` OkFile upload or URL failure: check `OKFILE_TOKEN`, `OKFILE_UPLOAD_URL`, network access, and account upload limits. The workflow retries transient failures automatically.
- `VTZ-E004` Alibaba submit or polling failure: check `DASHSCOPE_API_KEY`, `ALIYUN_WORKSPACE_ID`, `ALIYUN_REGION`, account balance, workspace ID, and service availability. Retryable HTTP/network failures are retried automatically.
- `VTZ-E005` AI segment contract / QA blocker: the AI runner should apply `final_qa_prompt.txt` and `final_qa_report.md` to repair `segments.txt`, then rerun. Ask the user only after two failed AI repair attempts or when domain judgment is needed.

## FAQ

- Do users need to remember commands? No. Users can paste a local video path or ask in natural language. Commands are for the AI runner.
- Why does the command stop after writing `prompt.txt`? This is expected. The AI creates `segments.txt`, then reruns the command to export.
- When should screen context be enabled? Only when visible text, charts, software UI, code, slide titles, or screen-only terms materially affect translation. Keep it off for normal talking-head, interview, podcast, or audio-led videos.
- Does QA failure mean the user must edit files? No. The AI runner should first apply `final_qa_prompt.txt` and rerun. Ask the user only after repeated repair failure or when domain judgment is needed.
- Why no backup ASR provider? The production path is intentionally fixed for consistency. Add Whisper/Groq/other providers only after a separate workflow decision.
- Does it support real-time subtitles? No. It processes recorded local media.
- Does it burn subtitles into video? No. It exports ASS/SRT only.
- Can it translate to non-Chinese target languages? The architecture can be extended, but the packaged QA/style/glossary path is optimized for Chinese output. Add target-specific prompt/glossary/QA/export rules first.
- Re-running repeats too much work: use the same `--run-id`; existing transcript, word stream, prompt, OkFile upload cache, and Alibaba task submission are reused when valid.
- Why has a long video been silent for a while? It should not be silent. For long videos, the AI runner must report every 10 minutes using `workflow_status.json` and console output. If no update appears, ask it to read `runs/<run-id>/work/workflow_status.json` and report the current stage.

## Anti-patterns

- Do not enable screen context by default; it costs time and attention.
- Do not treat very noisy, heavily accented, or overlapping-speaker audio as fully automatic.
- Do not switch ASR providers without validating word timestamps and alignment behavior.
- Do not ask the user to manually fix QA blockers before the AI has attempted `final_qa_prompt.txt`.
- Do not promise real-time subtitles or burned-in video output; this workflow exports subtitle files.
- Do not leave the user without updates during long ASR or segment-generation stages; long jobs require heartbeat updates even when the underlying API call is still running.
- Do not write one-off parallel translation helpers when `generate_segments_with_dashscope.py --concurrency` and `--cache` can do the same job reproducibly.

## Subtitle Quality Example

This is the kind of concise, viewing-first translation the workflow is designed to produce:

```text
SRC_DISPLAY: Now, this process is very important, because once you have simulated how much money you can make into the year...
ZH: 这个过程至关重要：一旦你模拟出全年潜在收益，再每天实盘交易，情绪干扰就会大幅降低
```

The goal is not literal word-for-word output. The goal is accurate timing, natural Chinese, domain-appropriate terms, and subtitle rhythm that does not overload the screen.

## Segment Contract

AI segmentation output must use this format:

```text
[SEG 0001]
SRC_RAW: exact words copied from the input with no punctuation changes
SRC_DISPLAY: Punctuated readable source-language sentence.
ZH: 中文翻译。
[/SEG]
```

Rules:

- `SRC_RAW` is the timestamp matching contract.
- Do not add punctuation, rewrite, insert words, remove words, or translate `SRC_RAW`.
- `SRC_DISPLAY` may repair capitalization, punctuation, readability, ASR split words, and proper names.
- `ZH` must translate the corrected meaning naturally into Chinese.
- Never copy ASR split-word errors into Chinese.
- The complete set of `SRC_RAW` segments must cover the entire normalized word stream exactly once, in order.
- Do not omit tiny ASR fragments such as `m.`, `um`, `okay`, `all right`, or half-sentences. Merge them with a neighbor when they are only oral filler.
- Split long ASR fragments near natural semantic pauses when they would be too long for comfortable subtitle reading.
- After writing `segments.txt`, check that each `ZH` still corresponds to the same segment's `SRC_RAW` and `SRC_DISPLAY`; do not allow a one-line shift in the translation column.

## ASR Segment Reference

The workflow writes:

```text
runs/<run-id>/work/asr_segments_reference.txt
```

This file is a checklist, not a mandatory subtitle boundary list. Use it to avoid missed fragments
and to spot ASR split-word/proper-name problems before translation. The AI should still segment by
subtitle viewing rhythm:

- merge very short oral filler with adjacent context;
- split long ASR chunks when they exceed natural subtitle length;
- keep every `SRC_RAW` span continuous and in source order;
- repair split words and proper names only in `SRC_DISPLAY` and `ZH`, never in `SRC_RAW`.

## Required Workflow Steps

The main wrapper performs these steps:

1. Check local environment.
2. Extract compact audio with ffmpeg.
3. Upload audio to OkFile.
4. Submit the OkFile URL to Fun-ASR.
5. Normalize Fun-ASR output into `transcript_words.json`.
6. Extract `word_table.json`, `word_stream.txt`, and `asr_segments_reference.txt`.
7. Optionally prepare `work/screen_context.txt` from local `ffmpeg` screenshots and the same multimodal AI when screen text matters.
8. Generate `prompt.txt` with the word stream, ASR segment reference, and optional screen context.
9. Wait for `segments.txt` if it does not exist.
10. Repair terms using `term_repair_rules.json`.
11. Validate `SRC_RAW` against `word_table.json` with `--auto-repair`: lines that a model
    lightly rewrote (up to 2 token edits) are restored verbatim from the original word
    stream, with a `.bak` backup and a printed before/after log.
12. Align segments to word timestamps.
13. Run the deterministic auto-fixer (`auto_fix_segments.py`): merge isolated oral fillers,
    dangling continuation fragments, flash subtitles under 0.8s, cues under 0.5s, and
    hanging connective boundaries followed by a short cue. Merges are skipped when the
    merged cue would exceed 8s, 24 source words, or 3 wrapped Chinese lines. `SRC_RAW`
    spans are only concatenated, never rewritten.
14. Run final QA, including coverage gaps, long segments, micro segments, reading speed, timing, ASR split words, and terminology warnings. If blockers remain, the wrapper aborts with pointers to `final_qa_report.md` and `final_qa_prompt.txt` instead of exporting.
15. Export SRT and ASS.
16. Copy final subtitles to `outputs`.
17. After the user accepts the subtitles, run cleanup in dry-run mode and only delete disposable files after confirmation.

## Output Naming

Default:

```text
<original-video-name>.zh-en.srt
<original-video-name>.zh-en.ass
```

For non-English source hints:

```text
<original-video-name>.zh-fr.srt
<original-video-name>.zh-es.srt
<original-video-name>.zh-it.srt
```

Override with:

```bash
--subtitle-tag custom-tag
```

## Subtitle Layout

Exported SRT/ASS cues use two lines by default:

```text
中文翻译
Source-language display line.
```

For normal English-source videos this means:

```text
中文翻译
English display line.
```

Use `--source-first` only if explicitly requested.

SRT is plain text and does not reliably control font size across players. Use it as a compatibility
format.

ASS is the preferred viewing format for bilingual subtitles. Bilingual ASS cues must be emitted as a
single `Dialogue` event with inline font-size tags, not as two separate `Dialogue` events. This keeps
Chinese and source-language lines on the same timing event and prevents players from reordering or
overlapping the two lines when long text wraps. Export must also insert manual line breaks into long Chinese text, because some ASS renderers do not auto-wrap continuous CJK text without spaces. Use about 36 Chinese-width characters per line, prefer punctuation within a 2-3 character adjustment window, and merge the final line back into the previous line if the final line would contain fewer than 4 non-space characters.

- Chinese line: font size `42`.
- Source-language line: font size `24`.
- Default layout: Chinese above, source language below.

The smaller source-language line keeps dense screen recordings readable while preserving the source
text for checking or learning.

Do not solve overlong subtitles by shrinking fonts further. Also do not mechanically split cues just
because the source-language line is long. Chinese is the primary viewing line.

Default visual guardrail:

- if the Chinese translation is estimated to fit within `3` visual lines, keep the cue unchanged;
- if the Chinese translation exceeds `3` visual lines, final QA should treat it as a blocker;
- when splitting is needed, re-understand the full segment and split at a weak semantic boundary;
- never split by blindly dividing source words or characters, because Chinese and source-language
  word order can differ; however, cues over 8s with more than 24 source-language words are
  treated as dense rhythm blockers unless the source is genuinely inseparable.

## Environment Checks

```bash
python scripts/check_env.py
python scripts/check_env.py --network
```

Local requirements:

- Python 3.9+
- ffmpeg
- valid `.env`

Install ffmpeg:

- macOS: `brew install ffmpeg`
- Windows: `winget install Gyan.FFmpeg`
- Linux: use the system package manager, for example `apt install ffmpeg`

## QA Rules

Final QA checks and required review items:

- alignment failures
- bad timing
- overlaps
- visual overflow from more than three estimated Chinese subtitle lines
- high Chinese reading speed
- undertranslated scope drift, where source text is substantial but Chinese is only a tiny fragment
- high source display speed as an informational hint only
- dense long subtitles: over 8s and over 24 source-language words; Chinese visual overflow is checked separately with the 3-line rule
- known bad domain terms
- remaining ASR split-word patterns
- when `screen_context.txt` is present, review visible screen terms and references against `SRC_DISPLAY` and `ZH`

Blockers stop export. Warnings and info do not mechanically stop export, but production delivery should include one focused polish pass on warnings that may affect meaning, untranslated fragments, ASR mishearing, term quality, awkward rhythm, or visible subtitle quality. Remaining warnings are acceptable only when they are false positives, low-value reading-speed hints, or repeated repair would cost disproportionate time. Do not use source-language length alone as a reason to split a segment; use it only together with long duration as a rhythm guardrail.

Domain QA rules are data-driven: `qa_bad_zh_terms` and `qa_split_display_patterns` inside the
term rules JSON drive the bad-term and split-word warnings, so custom domains provide one rules
file for both automatic repair and QA. The `long_duration` warning fires only when a cue exceeds
the duration limit AND shows Chinese reading pressure (high chars/s or 2+ wrapped lines), keeping
the warning list high-signal.

`python scripts/check_env.py --json` prints a machine-readable environment report for automation
runners.

## Completion Response Contract

After successful export, the AI runner must not stop after generating files. Return a concise chat response to the user with:

- ASS/SRT output paths;
- total elapsed time and available per-stage timing;
- ASR provider/model, orchestrating model, and fixed segment translation model (`qwen-mt-plus`);
- QA blocker count, warning count, and main warning types;
- a brief note on whether human spot-checking is recommended.

Use the printed final summary, `workflow_status.json`, and `final_qa_report.md` as the source of truth. If a field is unavailable, say `not recorded` rather than guessing. This chat response is part of the delivery contract, not an optional courtesy.

## Replacement Rule

Only replace the upload/ASR layer if explicitly requested. Any replacement must still produce:

```text
runs/<run-id>/transcript/transcript_words.json
```

It must contain reliable word-level timestamps. Without word-level timestamps, this workflow loses
its core alignment quality.

## Segment Translation Helper

`scripts/generate_segments_with_dashscope.py` is the fixed production path for creating `segments.txt`. With `--model auto`, it resolves to Alibaba Bailian `qwen-mt-plus`. Always keep `--cache` enabled so interrupted long videos resume instead of retranslating completed batches. Production runs use `--concurrency 1`; do not raise concurrency unless explicitly testing account rate limits.

```bash
python scripts/generate_segments_with_dashscope.py \
  runs/<run-id>/transcript/transcript_words.json \
  --out runs/<run-id>/work/segments.txt \
  --cache runs/<run-id>/work/dashscope_translation_cache.json \
  --model auto \
  --batch-size 40 \
  --concurrency 1
```

Do not replace this helper with a temporary hand-written concurrent translation script. Do not fallback to `qwen-plus` or other chat models on qwen-mt rate limits; slow down, resume from cache, and keep `qwen-mt-plus` as the fixed production model.

## Re-export Existing Runs

If ASR and `segments.txt` already exist and the task is only to apply updated QA/export/style rules, use:

```bash
python scripts/finalize_run.py runs/<run-id> \
  --output-base "<original-video-name>.zh-en" \
  --language en
```

This does not call OkFile or Fun-ASR. It runs term repair, validation, alignment, final QA, SRT/ASS export, and prints the final summary to the console/chat.

- Export display omits final Chinese soft punctuation (`。` / `，`) while preserving `？` / `！`. Style repair also changes awkward Chinese fragments such as `。因为`, `。也就是`, and `。现在 + number` into comma-linked clauses.

## Cleanup Completed Runs

After the user confirms that the final subtitles are accepted and no V2 edits are needed, clean disposable files from the run directory.

Preview first:

```bash
python scripts/clean_run.py runs/<run-id>
```

Delete after confirmation:

```bash
python scripts/clean_run.py runs/<run-id> --confirm
```

The cleaner removes upload audio copies, screenshot/screen-context scratch files, translation caches, backup fragments, temporary QA prompts, `.DS_Store`, and `__pycache__` folders. It keeps files needed for review and reproducibility, including `transcript_words.json`, `word_table.json`, `word_stream.txt`, `asr_segments_reference.txt`, `screen_context.txt`, `prompt.txt`, `segments.txt`, `aligned_segments.json`, `final_qa_report.md`, and exported subtitles.

Use `--aggressive` only when the final outputs are accepted and debugging/re-export is no longer needed.
