import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "skills" / "video-translate" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from transcribe_api import extract_audio  # noqa: E402
from video_to_subtitles import default_subtitle_tag, resolve_asr_media  # noqa: E402


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

    def test_prefers_same_basename_downloaded_audio(self):
        video = self.tmp_dir / "lesson.mp4"
        audio = self.tmp_dir / "lesson.m4a"
        video.write_bytes(b"video")
        audio.write_bytes(b"audio")
        self.assertEqual(resolve_asr_media(video), audio)

    def test_keeps_video_when_no_downloaded_audio_exists(self):
        video = self.tmp_dir / "lesson.mp4"
        video.write_bytes(b"video")
        self.assertEqual(resolve_asr_media(video), video)

    def test_uses_localized_subtitle_tags(self):
        self.assertEqual(default_subtitle_tag("en"), "中英双语字幕")
        self.assertEqual(default_subtitle_tag("fr"), "中法双语字幕")


if __name__ == "__main__":
    unittest.main()
