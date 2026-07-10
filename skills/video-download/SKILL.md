---
name: video-download
description: 使用 yt-dlp 与 FFmpeg 下载、保存、检查或提取公开视频/音频，覆盖 YouTube、Shorts、Vimeo、TikTok、Instagram、Bilibili 等 yt-dlp 支持的来源。Use when Codex is asked to inspect available video qualities, choose resolution/container/codec, download a permitted video or playlist, extract audio, merge streams, or save a media URL; list formats and confirm quality, output path, and filename before downloading.
---

# 一键加速视频下载

作者 / 工作流设计：`AI落地第四声`。本作者信息用于展示和来源识别，不添加额外授权限制。

这是一套面向视频和音频下载的确认优先工作流。用户只需要把链接交给 AI，AI 会先检查 `yt-dlp` 与 `ffmpeg` 环境，列出可用格式，解释实用选择，再确认画质、保存目录和文件名。只有用户确认后，AI 才会执行下载。

核心价值：避免拿到链接就直接下载，减少下错清晰度、下错容器、文件名混乱、HDR/编码不兼容、输出位置不清楚等问题。默认适用于 YouTube、YouTube Shorts、Vimeo、TikTok、Instagram、X/Twitter、Facebook、Twitch、Bilibili、Dailymotion、SoundCloud、Bandcamp、Reddit 及其他 `yt-dlp` 支持的来源；完整范围以 [yt-dlp 官方站点清单](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md) 为准。播放列表只在用户明确要求时处理。

快速开始：把视频链接发给 AI，并说明你想要“最高画质”“MP4 兼容”“小文件”“只要音频”或让 AI 推荐。默认推荐最高可用画质，而不是为了省空间主动降到 720p。下载若会继续做字幕翻译，AI 会在你指定的位置建立一个以中文视频名和视频 ID 命名的小工程文件夹；视频、音频和字幕都放在这里。`yt-dlp` 负责解析和下载；`ffmpeg` 负责把分离的视频与音频合并、转换容器、提取音频，以及需要时处理字幕、封面和元数据。

效果示例：

```text
用户：帮我下载这个 YouTube 视频，尽量清晰。
AI：我会先列出可用格式，然后给你几个选择：最高画质、MP4 兼容、较小文件、仅音频。确认画质、保存路径和文件名后再下载。
```

以下从 “English Execution Contract” 开始是给 AI 执行者读取的正式规则；上面的中文说明只用于 SkillHub、ClawHub、skills.sh 和用户理解，不替代执行合同。

# English Execution Contract

Use this skill for reviewed video/audio downloads with `yt-dlp`. Do not download immediately after the user provides a link. First inspect available formats, summarize practical choices, and ask the user to choose. Before downloading, also confirm the download path and filename. Download only after the user confirms all required choices or explicitly delegates them.

## Workflow

1. Check tools if not already confirmed:

```bash
command -v yt-dlp
command -v ffmpeg
```

2. List available formats:

```bash
yt-dlp --no-playlist -F "VIDEO_URL"
```

Use `--no-playlist` unless the user explicitly asks for a playlist.

3. Summarize the useful choices:
   - Best quality (default recommendation): highest available video plus best audio. Prefer H.264 video plus M4A/AAC in `mp4` when that preserves the highest available resolution; otherwise explain the container tradeoff.
   - MP4 compatibility: H.264 video plus M4A/AAC audio, usually `mp4`.
   - Smaller file: 1080p, 720p, or another clear cap.
   - Audio only: best audio or M4A compatibility.

Mention format IDs or selectors, resolution, FPS, HDR/SDR, video codec, audio codec, estimated size when visible, and container.

4. Ask the user which quality or format to download. Do not run the download command until they confirm.

5. Confirm the parent download location and create a media project folder.
   - Treat every download that may continue to subtitle translation as one media project, not a loose collection of files.
   - Use the confirmed location as `PARENT_DIR`, then create `PROJECT_DIR` named `<localized video title> [<video id>]` beneath it. Localize the title to the user's requested language when asked.
   - Save the video, an explicitly downloaded audio-only file, ASS/SRT outputs, and hidden working artifacts under `PROJECT_DIR`. Do not leave related files in the parent directory.
   - Pass the same `PROJECT_DIR` to video translation as both its `--outputs-dir` and the parent of its hidden `.work/` directory.

6. Confirm the filename.
   - Propose a default filename from the video metadata, normally:

```text
%(upload_date>%Y-%m-%d)s - %(title).200B [%(id)s].%(ext)s
```

   - Ask whether the user wants to update the filename.
   - If yes, ask them to send the filename directly. Preserve or add the final extension based on the chosen container.
   - Keep `[%(id)s]` in the default name to avoid collisions and preserve the source video ID, but remove it if the user requests a cleaner name.
   - Use the confirmed filename or template as `OUTPUT_NAME`. When a localized project title is used, keep the same localized basename for video, audio, and subtitles.

## Commands

Use explicit reviewed IDs when possible:

```bash
yt-dlp --no-playlist --windows-filenames \
  -f "VIDEO_ID+AUDIO_ID" \
  --merge-output-format mkv \
  -P "OUTPUT_DIR" \
  -o "OUTPUT_NAME" \
  "VIDEO_URL"
```

Use best quality after the user delegates selection:

```bash
yt-dlp --no-playlist --windows-filenames \
  -f "bv*+ba/b" \
  --merge-output-format mkv \
  -P "OUTPUT_DIR" \
  -o "OUTPUT_NAME" \
  "VIDEO_URL"
```

Use MP4 compatibility after confirmation:

```bash
yt-dlp --no-playlist --windows-filenames \
  -f "bv*[ext=mp4][vcodec^=avc1]+ba[ext=m4a]/b[ext=mp4]/b" \
  --merge-output-format mp4 \
  -P "OUTPUT_DIR" \
  -o "OUTPUT_NAME" \
  "VIDEO_URL"
```

Use audio only after confirmation:

```bash
yt-dlp --no-playlist --windows-filenames \
  -f "ba" \
  -P "OUTPUT_DIR" \
  -o "OUTPUT_NAME" \
  "VIDEO_URL"
```

## Final Response

After downloading, report the saved path, file size, selected format IDs or selector, confirmed output directory, confirmed filename, and any important caveats such as HDR, MKV playback, subtitles, or audio language.

Remind the user to download only content they have permission to save or use when relevant.
