---
name: video-translate
description: 将用户明确选择的本地视频或音频转为中英双语 ASS/SRT 字幕。仅在用户确认媒体路径、输出目录及向 OkFile 和阿里云上传音频/文本处理的同意后运行。Use only after explicit user consent to process a selected local media file with OkFile, Alibaba Fun-ASR, and qwen-mt-plus.
permissions:
  - file_read
  - file_write
  - env
  - network
  - shell
metadata:
  openclaw:
    requires:
      env:
        - DASHSCOPE_API_KEY
        - ALIYUN_WORKSPACE_ID
        - OKFILE_TOKEN
      bins:
        - python3
        - ffmpeg
    primaryEnv: DASHSCOPE_API_KEY
    envVars:
      - name: DASHSCOPE_API_KEY
        required: true
        description: Alibaba DashScope credential used only for Fun-ASR and qwen-mt-plus requests.
      - name: ALIYUN_WORKSPACE_ID
        required: true
        description: Alibaba Model Studio workspace identifier used to construct an Alibaba HTTPS endpoint.
      - name: OKFILE_TOKEN
        required: true
        description: OkFile API credential used only as an HTTPS authentication header for the selected audio upload.
      - name: ALIYUN_REGION
        required: false
        description: Optional Alibaba region; defaults to cn-beijing.
---

# 人工级视频字幕翻译

作者 / 工作流设计：`AI落地第四声`。本作者信息用于展示和来源识别，不添加额外授权限制。

这是一套面向本地录制视频的高质量字幕翻译工作流。它使用词级时间戳、AI 语义分段、术语修复和自动 QA，导出中文字幕在上、原文在下的 ASS/SRT 字幕。默认目标语言为中文，常用源语言为英语、法语、西班牙语和意大利语。

快速开始：准备 OkFile API Key、阿里 DashScope API Key、阿里工作空间 ID，并提供本地视频或音频路径。AI 仅在你明确确认媒体路径、输出位置和外发处理同意后，才会读取本机 `.env`、上传选定音频并运行固定生产流程。长视频开始前必须说明大致耗时，执行中每 10 分钟反馈状态。

## 首次安装提示

首次使用或环境检查发现缺少凭据时，先向用户说明：本工作流会在本地准备可上传音频，使用 OkFile 生成临时链接，再由阿里 Fun-ASR 产生词级时间戳；随后固定使用 `qwen-mt-plus` 完成分段翻译，最后由当前 Agent 做对齐、术语修复、QA 和 ASS/SRT 导出。

- 编排推荐：在 Codex/Cursor 等 Coding Agent 中使用 GPT-5.5 级模型，负责长任务调度、时间轴对齐、QA 修复与交付总结；在 WorkBuddy 中推荐 DeepSeek V4 Pro。它们不替换转写或翻译模型。
- 转写固定为阿里 Fun-ASR，因为它支持长音频任务和词级时间戳，这是字幕精确对齐的基础。
- 分段翻译固定为阿里 `qwen-mt-plus`，因为它与当前术语规则、缓存恢复和串行稳定性策略匹配。
- 本机需要 `DASHSCOPE_API_KEY`、`ALIYUN_WORKSPACE_ID`、`OKFILE_TOKEN`。环境缺失时，先说明用途并询问用户是否同意创建并打开本机 `.env`；只有得到明确同意后才执行 `bash scripts/open_env_setup.sh --open`。不得让用户在聊天中发送密钥。
- 想了解完整细节时，查看 [视频翻译工作流说明书](../../docs/video-translate/视频翻译工作流说明书.md)。

用户示例：

```text
把 /Users/me/Desktop/lesson.mp4 翻译成中文字幕。保留原文，视频里的 PPT 文字也很重要。
```

## Execution Contract

Use this skill only for local recorded media. Before every production run, read [the full execution contract](references/execution-contract.md) in full. It defines the segment format, QA gates, repair rules, export layout, long-run behavior, and cleanup rules.

Keep this production stack fixed unless the user explicitly requests an engineering redesign and accepts revalidation:

1. Reuse a supplied audio input or a same-basename audio-only download when present; otherwise extract compact audio locally with `ffmpeg`.
2. Upload through OkFile and submit the resulting URL to Alibaba Fun-ASR.
3. Use Fun-ASR word timestamps as the alignment source of truth.
4. Generate `segments.txt` with `qwen-mt-plus`.
5. Repair terms, validate `SRC_RAW`, align timestamps, run auto-fixes and final QA, then export ASS/SRT.

Do not silently switch ASR providers, use local Whisper, add fallback model paths, install system tools, or reveal secrets.

## Before Running

Run commands from this skill folder. On a new device or unverified environment, run the local-only check:

```bash
python scripts/check_env.py
```

Confirm only these user-facing inputs unless already clear:

1. Source language. Default: English (`--language en`).
2. Target language. Default: Chinese; other targets require target-specific rules before production quality is claimed.
3. Whether screen context is needed for important visible text, slides, charts, UI, code, signs, or images. Keep it off by default.
4. Subtitle output directory. Default: project `outputs/`; confirm any different path. When the media came from the download Skill, use its media project folder so video, audio, ASS/SRT, and hidden `.work/` artifacts stay together.
5. Explicit consent for external processing: explain that the selected audio is uploaded to `https://www.okfile.com`, its temporary URL is sent to Alibaba Fun-ASR, and subtitle text is sent to Alibaba qwen-mt-plus. Do not proceed without an affirmative answer.

Do not ask ordinary users to choose ASR, segment-generation, or orchestration models.

## Run And Recover

Start a normal run with:

```bash
python scripts/video_to_subtitles.py "/absolute/path/to/video-or-audio.mp4" --language en --confirm-external-processing
```

Add `--outputs-dir "<project-path>"` after the user confirms the media project folder. The default working directory becomes `<project-path>/.work/`, keeping intermediate files out of the Skill source directory. For screen-recording guidance, read [screen context rules](references/screen_context.md) before generating screenshots.

When a run fails, use `workflow_status.json`, `final_qa_report.md`, `final_qa_prompt.txt`, and `python scripts/check_env.py --json`. Repair `segments.txt` automatically before asking the user; ask only after two failed repair attempts or when domain judgment is necessary. Reuse the same `--run-id` for retries.

## Delivery Rules

Do not export when QA has blockers. After success, report the ASS path, SRT path, elapsed time, models used, QA blocker/warning counts, and any focused spot-check recommendation.

The repository-level product guide is outside the installable skill package. Do not treat product documentation as the execution contract.
