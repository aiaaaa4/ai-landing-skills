---
name: video-download
description: Review-first workflow for downloading videos or audio with yt-dlp. Use when Codex is asked to download, save, extract audio from, or inspect available qualities for YouTube, Shorts, playlists, or any yt-dlp-supported video URL. Always list formats first, confirm the quality, confirm the download path and filename, then download only after confirmation.
---

# Video Download

## Rule

Never download immediately after the user provides a video link. First inspect available formats, summarize practical choices, and ask the user to choose. Before downloading, also confirm the download path and filename. Download only after the user confirms all required choices or explicitly delegates them.

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
   - Best quality: highest useful video plus best audio, usually `mkv`.
   - MP4 compatibility: H.264 video plus M4A/AAC audio, usually `mp4`.
   - Smaller file: 1080p, 720p, or another clear cap.
   - Audio only: best audio or M4A compatibility.

Mention format IDs or selectors, resolution, FPS, HDR/SDR, video codec, audio codec, estimated size when visible, and container.

4. Ask the user which quality or format to download. Do not run the download command until they confirm.

5. Confirm the download path.
   - On the first run in a thread or project, propose `/Users/aarondong/Desktop/video-download skill/outputs` as the default path and ask the user to confirm it.
   - On later runs, ask whether to save to the existing default path.
   - If the user wants a different path, ask them to send the new path directly.
   - Use the confirmed path as `OUTPUT_DIR`.

6. Confirm the filename.
   - Propose a default filename from the video metadata, normally:

```text
%(upload_date>%Y-%m-%d)s - %(title).200B [%(id)s].%(ext)s
```

   - Ask whether the user wants to update the filename.
   - If yes, ask them to send the filename directly. Preserve or add the final extension based on the chosen container.
   - Keep `[%(id)s]` in the default name to avoid collisions and preserve the source video ID, but remove it if the user requests a cleaner name.
   - Use the confirmed filename or template as `OUTPUT_NAME`.

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
