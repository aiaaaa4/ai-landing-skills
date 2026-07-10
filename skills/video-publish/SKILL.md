---
name: video-publish
description: 使用本地 FFmpeg 将用户指定的视频快速封装为发布版 MP4，可烧录字幕、添加开篇免责声明、叠加动态或固定文字水印、裁切片段并优化网页播放。Use when a user explicitly asks to package a local video for publishing with a disclaimer, burned subtitles, a watermark, trim, or fast MP4 export.
permissions:
  - file_read
  - file_write
  - shell
  - network
metadata:
  openclaw:
    requires:
      bins:
        - ffmpeg
        - ffprobe
    skillKey: video-publish
---

# 极简视频封装

作者 / 工作流设计：`AI落地第四声`。这是纯本地 FFmpeg 后处理：不上传视频、不读取凭据、不调用云端 API。只有首次缺少 FFmpeg 且用户明确要求安装时，才会通过系统包管理器安装它。

适用于已经下载或翻译完成的视频项目。默认保留原分辨率、原音频与元数据，输出适合网页和社交平台播放的 MP4。

## Environment

如果当前对话已经确认 `video-download` 或 `video-translate` 正常使用过 FFmpeg，可直接执行封装。否则先运行：

```bash
python scripts/check_ffmpeg.py
```

没有 FFmpeg 时，先告知用户安装方式；用户明确同意安装后才运行：

```bash
python scripts/check_ffmpeg.py --install
```

macOS 优先使用 Homebrew；脚本不使用 `sudo`，也不会自动安装其他软件。

## Required Confirmation

每次任务都先通过对话确认以下内容。除非用户明确委托默认值，否则不要跳过。

1. **免责声明**：是否需要；确认文字、`2-3` 秒时长、全屏黑底或半透明覆盖，以及是否静音该时段原音频。
2. **字幕烧录**：是否需要；确认 ASS/SRT 文件路径。默认优先 ASS，保留原字幕则不烧录。
3. **水印**：是否需要；确认文字内容、动态漂移或固定角落、位置、透明度。水印文字为空时不添加。
4. **输出**：确认输出 MP4 的绝对路径与文件名；已有同名文件时，必须再确认是否覆盖。
5. **专业封装选项**：是否裁去开头/结尾、是否保留原分辨率、画质优先或速度优先、是否需要网页快速起播。默认是保留原分辨率、速度与画质平衡、启用 `faststart`、不裁切。

建议的默认免责声明：`本视频仅供学习交流，不构成任何建议。`。不要把它当作自动默认文本，仍要用户确认。

## Run

完成确认后，从本 skill 目录运行。示例：

```bash
python scripts/package_video.py \
  "/absolute/path/source.mp4" \
  --output "/absolute/path/source-发布版.mp4" \
  --disclaimer-text "本视频仅供学习交流，不构成任何建议。" \
  --disclaimer-seconds 3 \
  --mute-disclaimer-audio \
  --subtitle "/absolute/path/source.中英双语字幕.ass" \
  --watermark-text "AI落地第四声 · aiaaaa4" \
  --watermark-mode drift \
  --quality high
```

常用选项：

- `--disclaimer-mode full-screen|overlay`：默认全屏黑底；`overlay` 保留原视频画面。
- `--watermark-mode drift|top-right|top-left|bottom-right|bottom-left`：默认 `drift`，在画面上方缓慢移动。
- `--watermark-opacity 0.45`：范围 `0.05-1.0`。
- `--trim-start 00:00:05 --trim-duration 00:01:20`：只封装指定片段。
- `--encoder auto|h264_videotoolbox|libx264`：`auto` 在 Mac 优先硬件编码；`libx264` 更慢但便于跨平台复现。
- `--dry-run`：只打印最终 FFmpeg 命令，不写入视频。
- `--overwrite`：只在用户已确认覆盖时添加。

脚本会拒绝输入与输出相同、找不到字幕、非 MP4 输出、未安装 FFmpeg，以及未明确 `--overwrite` 的同名输出。

## Delivery

完成后报告：输出路径、文件大小、是否烧录字幕、免责声明样式与时长、水印模式、编码器和裁切范围。不要声称已添加某项未确认的效果。
