---
name: video-publish
description: 使用本地 FFmpeg 从视频前半段轻量抽取候选封面，并将选定封面与固定免责声明作为短片头拼接到原视频；默认不重编码原视频主体。也支持明确需要时的字幕烧录、水印、裁切与完整重编码。Use when a user asks to prepare a local video for publishing, extract cover candidates, prepend a cover or disclaimer, or explicitly apply burned subtitles, watermarks, or full-video filters.
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

作者 / 工作流设计：`AI落地第四声`。这是纯本地 FFmpeg 后处理：不上传视频、不读取凭据、不调用云端 API。

默认流程是：从视频前半段抽取 `5` 张封面候选，等待用户选择；将选定封面作为开头 `3` 帧，再显示固定免责声明 `2` 秒，最后无损拼接原视频。只编码短片头，原视频主体使用码流复制。

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

每次任务都先通过对话确认以下内容：

1. **封面**：使用现有图片，还是从视频前半段抽取 `5` 张候选；抽取后必须展示候选并等待用户选择。
2. **片头时长**：封面默认 `3` 帧，在 25fps 视频中为 `0.12` 秒；免责声明默认使用 `assets/disclaimer-zh-en-1920x1080.png` 并显示 `2` 秒。
3. **输出**：确认 MP4 的绝对路径；已有同名文件时必须再次确认覆盖。
4. **高级处理**：只有用户明确要求字幕烧录、水印、裁切或画面滤镜时才使用全片重编码，并提前说明画质、体积和耗时影响。

YouTube、B站等平台的投稿封面应同时使用选中的独立 PNG；不要假设平台一定采用视频第一帧。

## Lightweight Run

抽取前半段的五张候选封面：

```bash
python scripts/extract_covers.py \
  "/absolute/path/source.mp4" \
  --output-dir "/absolute/path/covers"
```

用户选择后，轻量拼接封面、免责声明与原视频：

```bash
python scripts/prepend_intro.py \
  "/absolute/path/source.mp4" \
  --cover-image "/absolute/path/covers/cover-03.png" \
  --output "/absolute/path/source-发布版.mp4"
```

使用 `--cover-frames 3` 按帧控制封面；使用 `--cover-seconds 0.1` 时脚本会向上对齐到完整帧。`--preview-content-seconds 8` 可先输出短预览。默认只支持将短片头无损拼接到 H.264 `yuv420p` + AAC MP4；其他编码格式应明确告知用户并改用完整重编码。

## Advanced Run

只有用户明确要求烧录字幕、水印或其他全片滤镜时，才运行 `scripts/package_video.py`。这些操作会重新编码完整视频；不要为了添加静态封面或免责声明而调用它。

脚本会拒绝输入与输出相同、找不到字幕、非 MP4 输出、未安装 FFmpeg，以及未明确 `--overwrite` 的同名输出。

## Delivery

完成后报告：候选封面位置、用户选中的封面、封面和免责声明时长、输出路径，以及原视频主体是否重编码。默认轻量流程必须明确报告 `source_video_reencoded: false`。
