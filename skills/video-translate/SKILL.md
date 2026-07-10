---
name: video-translate
description: 本地视频高质量字幕翻译工作流，面向本地录制视频，解决普通字幕断句生硬、时间轴不准、术语不地道、长句堆叠和中外文错位问题。用户只需提供本地视频路径；AI 会确认源语言、目标语言、屏幕上下文和导出目录，再用 OkFile、阿里 Fun-ASR、qwen-mt-plus、术语修复和 QA 导出 ASS/SRT。Use when creating subtitles from local videos with word-level alignment, AI translation, terminology repair, QA, and ASS/SRT export.
---

# 人工级视频字幕翻译

作者 / 工作流设计：`AI落地第四声`。本作者信息用于展示和来源识别，不添加额外授权限制。

这是一套面向本地录制视频的高质量字幕翻译工作流。它使用词级时间戳、AI 语义分段、术语修复和自动 QA，导出中文字幕在上、原文在下的 ASS/SRT 字幕。默认目标语言为中文，常用源语言为英语、法语、西班牙语和意大利语。

快速开始：准备 OkFile API Key、阿里 DashScope API Key、阿里工作空间 ID，并提供本地视频路径。AI 会检查环境、确认必要输入并运行固定生产流程。长视频开始前必须说明大致耗时，执行中每 10 分钟反馈状态。

用户示例：

```text
把 /Users/me/Desktop/lesson.mp4 翻译成中文字幕。保留原文，视频里的 PPT 文字也很重要。
```

## Execution Contract

Use this skill only for local recorded media. Before every production run, read [the full execution contract](references/execution-contract.md) in full. It defines the segment format, QA gates, repair rules, export layout, long-run behavior, and cleanup rules.

Keep this production stack fixed unless the user explicitly requests an engineering redesign and accepts revalidation:

1. Extract compact audio locally with `ffmpeg`.
2. Upload through OkFile and submit the resulting URL to Alibaba Fun-ASR.
3. Use Fun-ASR word timestamps as the alignment source of truth.
4. Generate `segments.txt` with `qwen-mt-plus`.
5. Repair terms, validate `SRC_RAW`, align timestamps, run auto-fixes and final QA, then export ASS/SRT.

Do not silently switch ASR providers, use local Whisper, add fallback model paths, install system tools, or reveal secrets.

## Before Running

Run commands from this skill folder. On a new device or unverified environment, run:

```bash
python scripts/check_env.py
python scripts/check_env.py --network
```

Confirm only these user-facing inputs unless already clear:

1. Source language. Default: English (`--language en`).
2. Target language. Default: Chinese; other targets require target-specific rules before production quality is claimed.
3. Whether screen context is needed for important visible text, slides, charts, UI, code, signs, or images. Keep it off by default.
4. Subtitle output directory. Default: project `outputs/`; confirm any different path.

Do not ask ordinary users to choose ASR, segment-generation, or orchestration models.

## Run And Recover

Start a normal run with:

```bash
python scripts/video_to_subtitles.py "/absolute/path/to/video.mp4" --language en
```

Add `--outputs-dir "<path>"` only after the user confirms a different export location. For screen-recording guidance, read [screen context rules](references/screen_context.md) before generating screenshots.

When a run fails, use `workflow_status.json`, `final_qa_report.md`, `final_qa_prompt.txt`, and `python scripts/check_env.py --json`. Repair `segments.txt` automatically before asking the user; ask only after two failed repair attempts or when domain judgment is necessary. Reuse the same `--run-id` for retries.

## Delivery Rules

Do not export when QA has blockers. After success, report the ASS path, SRT path, elapsed time, models used, QA blocker/warning counts, and any focused spot-check recommendation.

The repository-level product guide is outside the installable skill package. Do not treat product documentation as the execution contract.
