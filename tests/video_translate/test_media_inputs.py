import sys
import tempfile
import unittest
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "skills" / "video-translate" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from transcribe_api import extract_audio, should_delete_prepared_audio, validate_workflow_audio  # noqa: E402
from generate_segments_with_dashscope import build_chunks  # noqa: E402
from source_subtitle_reference import load_source_subtitle, references_by_asr_segment  # noqa: E402
from video_to_subtitles import (  # noqa: E402
    bind_translation_provider,
    cleanup_workflow_inputs,
    default_subtitle_tag,
    resolve_asr_media,
    resolve_source_subtitle,
    ensure_ai_segments,
    main,
)


class MediaInputTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_reuses_direct_audio_without_ffmpeg(self):
        audio = self.tmp_dir / "lesson.m4a"
        audio.write_bytes(b"audio")
        self.assertEqual(extract_audio(audio, self.tmp_dir / "out"), audio)

    def test_never_deletes_caller_supplied_audio(self):
        audio = self.tmp_dir / "lesson.m4a"
        audio.write_bytes(b"audio")
        self.assertFalse(should_delete_prepared_audio(audio, audio, keep_audio=False))

    def test_deletes_only_audio_generated_from_video(self):
        video = self.tmp_dir / "lesson.mp4"
        generated = self.tmp_dir / "transcript" / "api_upload_audio.mp3"
        video.write_bytes(b"video")
        generated.parent.mkdir()
        generated.write_bytes(b"audio")
        self.assertTrue(should_delete_prepared_audio(video, generated, keep_audio=False))
        self.assertFalse(should_delete_prepared_audio(video, generated, keep_audio=True))

    def test_user_facing_workflow_rejects_direct_audio(self):
        audio = self.tmp_dir / "lesson.m4a"
        audio.write_bytes(b"audio")
        old_argv = sys.argv
        try:
            sys.argv = ["video_to_subtitles.py", str(audio), "--confirm-external-processing"]
            self.assertEqual(main(), 2)
        finally:
            sys.argv = old_argv

    def test_transcribe_helper_rejects_direct_audio_without_internal_marker(self):
        from transcribe_api import main as transcribe_main

        audio = self.tmp_dir / "lesson.m4a"
        audio.write_bytes(b"audio")
        old_argv = sys.argv
        try:
            sys.argv = ["transcribe_api.py", str(audio), "--confirm-external-processing"]
            self.assertEqual(transcribe_main(), 2)
        finally:
            sys.argv = old_argv

    def test_workflow_audio_must_match_video_name_and_project(self):
        video = self.tmp_dir / "lesson.mp4"
        video.write_bytes(b"video")
        hidden = self.tmp_dir / ".work" / "input" / "lesson.m4a"
        hidden.parent.mkdir(parents=True)
        hidden.write_bytes(b"audio")
        self.assertEqual(validate_workflow_audio(hidden, video), hidden.resolve())

        unrelated = self.tmp_dir / ".work" / "input" / "other.m4a"
        unrelated.write_bytes(b"audio")
        with self.assertRaisesRegex(RuntimeError, "basename must match"):
            validate_workflow_audio(unrelated, video)

    def test_prefers_same_basename_downloaded_audio(self):
        video = self.tmp_dir / "lesson.mp4"
        audio = self.tmp_dir / "lesson.m4a"
        video.write_bytes(b"video")
        audio.write_bytes(b"audio")
        self.assertEqual(resolve_asr_media(video), audio)

    def test_prefers_hidden_combined_workflow_audio(self):
        video = self.tmp_dir / "lesson.mp4"
        hidden = self.tmp_dir / ".work" / "input" / "lesson.m4a"
        hidden.parent.mkdir(parents=True)
        video.write_bytes(b"video")
        hidden.write_bytes(b"audio")
        self.assertEqual(resolve_asr_media(video), hidden)

    def test_discovers_and_cleans_hidden_source_inputs(self):
        video = self.tmp_dir / "lesson.mp4"
        hidden_dir = self.tmp_dir / ".work" / "input"
        hidden_dir.mkdir(parents=True)
        audio = hidden_dir / "lesson.m4a"
        subtitle = hidden_dir / "lesson.原语言字幕.srt"
        video.write_bytes(b"video")
        audio.write_bytes(b"audio")
        subtitle.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")
        self.assertEqual(resolve_source_subtitle(video, None), subtitle.resolve())
        removed = cleanup_workflow_inputs(video, [audio, subtitle])
        self.assertEqual(set(removed), {audio.resolve(), subtitle.resolve()})
        self.assertFalse(hidden_dir.exists())

    def test_cleanup_never_deletes_external_user_inputs(self):
        video = self.tmp_dir / "lesson.mp4"
        external_audio = self.tmp_dir / "lesson.m4a"
        external_subtitle = self.tmp_dir / "lesson.srt"
        video.write_bytes(b"video")
        external_audio.write_bytes(b"audio")
        external_subtitle.write_text("subtitle", encoding="utf-8")
        self.assertEqual(cleanup_workflow_inputs(video, [external_audio, external_subtitle]), [])
        self.assertTrue(external_audio.exists())
        self.assertTrue(external_subtitle.exists())

    def test_source_subtitle_corrects_display_but_preserves_asr_raw_words(self):
        subtitle = self.tmp_dir / "source.srt"
        subtitle.write_text(
            "1\n00:00:00,000 --> 00:00:04,500\n"
            "If price breaks above the prior day high, we do not chase the move.\n",
            encoding="utf-8",
        )
        transcript = {
            "segments": [
                {
                    "start": 0.0,
                    "end": 4.5,
                    "text": "If price breaks above the prior day hi we do not chase the move",
                    "words": [
                        {"word": word}
                        for word in "If price breaks above the prior day hi we do not chase the move".split()
                    ],
                }
            ]
        }
        cues = load_source_subtitle(subtitle)
        references = references_by_asr_segment(transcript, cues)
        chunks = build_chunks(transcript, 18, references)
        self.assertTrue(any(chunk.reference_used for chunk in chunks))
        self.assertIn("high", " ".join(chunk.source_display for chunk in chunks))
        self.assertEqual(
            " ".join(chunk.source_raw for chunk in chunks),
            "if price breaks above the prior day hi we do not chase the move",
        )

    def test_webvtt_minute_timestamp_is_supported(self):
        subtitle = self.tmp_dir / "source.vtt"
        subtitle.write_text("WEBVTT\n\n00:01.500 --> 00:03.000\nHello world\n", encoding="utf-8")
        cues = load_source_subtitle(subtitle)
        self.assertEqual(len(cues), 1)
        self.assertEqual((cues[0].start, cues[0].end, cues[0].text), (1.5, 3.0, "Hello world"))

    def test_unrelated_source_subtitle_falls_back_to_asr_text(self):
        transcript = {
            "segments": [
                {
                    "start": 0.0,
                    "end": 2.0,
                    "text": "Price broke above resistance",
                    "words": [{"word": word} for word in "Price broke above resistance".split()],
                }
            ]
        }
        chunks = build_chunks(transcript, 18, {0: "Completely unrelated cooking instructions"})
        self.assertFalse(any(chunk.reference_used for chunk in chunks))
        self.assertIn("Price broke above resistance", chunks[0].source_display)

    def test_existing_segments_reject_changed_source_reference(self):
        work_dir = self.tmp_dir / "work"
        transcript_dir = self.tmp_dir / "transcript"
        work_dir.mkdir()
        transcript_dir.mkdir()
        subtitle = self.tmp_dir / "source.srt"
        subtitle.write_text("reference v1", encoding="utf-8")
        translation_context = self.tmp_dir / "translation-context.json"
        translation_context.write_text(
            json.dumps({"stage": "translation-context", "domains": "test", "terms": [], "tm_list": []}),
            encoding="utf-8",
        )
        (work_dir / "segments.txt").write_text("segments", encoding="utf-8")
        (work_dir / "segment_generation_meta.json").write_text(
            json.dumps(
                {
                    "source_subtitle": str(subtitle),
                    "source_subtitle_sha256": hashlib.sha256(subtitle.read_bytes()).hexdigest(),
                    "translation_context_sha256": hashlib.sha256(translation_context.read_bytes()).hexdigest(),
                }
            ),
            encoding="utf-8",
        )
        ensure_ai_segments(work_dir, transcript_dir, "en", "test", subtitle, translation_context)
        subtitle.write_text("reference v2", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "different source subtitle"):
            ensure_ai_segments(work_dir, transcript_dir, "en", "test", subtitle, translation_context)

    def test_run_cannot_mix_translation_providers(self):
        work_dir = self.tmp_dir / "work"
        work_dir.mkdir()
        bind_translation_provider(work_dir, "agent")
        with self.assertRaisesRegex(RuntimeError, "already bound"):
            bind_translation_provider(work_dir, "qwen-mt-plus")

    def test_legacy_qwen_metadata_prevents_agent_switch(self):
        work_dir = self.tmp_dir / "work"
        work_dir.mkdir()
        (work_dir / "segment_generation_meta.json").write_text(
            json.dumps({"model": "qwen-mt-plus"}),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(RuntimeError, "translation_provider=qwen-mt-plus"):
            bind_translation_provider(work_dir, "agent")

    def test_keeps_video_when_no_downloaded_audio_exists(self):
        video = self.tmp_dir / "lesson.mp4"
        video.write_bytes(b"video")
        self.assertEqual(resolve_asr_media(video), video)

    def test_uses_localized_subtitle_tags(self):
        self.assertEqual(default_subtitle_tag("en"), "中英双语字幕")
        self.assertEqual(default_subtitle_tag("fr"), "中法双语字幕")


if __name__ == "__main__":
    unittest.main()
