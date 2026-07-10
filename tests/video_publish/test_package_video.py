import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "skills" / "video-publish" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from package_video import (  # noqa: E402
    build_command,
    build_video_filter,
    constrained_bitrates,
    filter_escape,
    parse_args,
    validate_args,
    wrap_disclaimer_text,
)


class VideoPublishTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(self.tmp.name)
        self.source = self.tmp_dir / "source.mp4"
        self.subtitle = self.tmp_dir / "subtitle.ass"
        self.font = self.tmp_dir / "font.ttf"
        self.output = self.tmp_dir / "published.mp4"
        self.source.write_bytes(b"video")
        self.subtitle.write_text("[Script Info]\n", encoding="utf-8")
        self.font.write_bytes(b"font")

    def tearDown(self):
        self.tmp.cleanup()

    def parse(self, *extra: str):
        with patch.object(sys, "argv", ["package_video.py", str(self.source), "--output", str(self.output), *extra]):
            return parse_args()

    def test_escapes_filter_text(self):
        escaped = filter_escape("AI: 50%, [demo]\\next")
        self.assertIn(r"\:", escaped)
        self.assertIn(r"\,", escaped)
        self.assertIn(r"\[", escaped)
        self.assertIn(r"\\", escaped)

    def test_builds_confirmed_publish_filter(self):
        args = self.parse(
            "--subtitle",
            str(self.subtitle),
            "--disclaimer-text",
            "仅供学习",
            "--font",
            str(self.font),
            "--watermark-text",
            "AI落地第四声 · aiaaaa4",
            "--watermark-mode",
            "drift",
            "--mute-disclaimer-audio",
        )
        source, output, subtitle = validate_args(args)
        video_filter = build_video_filter(args, subtitle)
        self.assertIn("subtitles=", video_filter)
        self.assertIn("drawbox=", video_filter)
        self.assertIn("drawtext=", video_filter)
        with patch("package_video.choose_encoder", return_value="libx264"):
            command, encoder = build_command(args, source, output, subtitle, "ffmpeg")
        self.assertEqual(encoder, "libx264")
        self.assertIn("-movflags", command)
        self.assertIn("+faststart", command)
        self.assertIn("-af", command)
        self.assertIn("-c:a", command)

    def test_existing_output_requires_overwrite(self):
        self.output.write_bytes(b"existing")
        args = self.parse()
        with self.assertRaisesRegex(RuntimeError, "--overwrite"):
            validate_args(args)

    def test_long_disclaimer_is_wrapped_with_a_smaller_font(self):
        disclaimer = "免责声明 / Disclaimer\n" + "本视频由我方搬运并翻译，仅作非商业用途，旨在学习、交流与信息分享。" * 12
        wrapped = wrap_disclaimer_text(disclaimer)
        self.assertGreater(wrapped.count("\n"), 8)
        args = self.parse("--disclaimer-text", disclaimer, "--font", str(self.font))
        source, output, subtitle = validate_args(args)
        self.assertEqual(source, self.source.resolve())
        self.assertIsNone(subtitle)
        self.assertIn("fontsize=h/36", build_video_filter(args, subtitle))
        self.assertIn("textfile='/tmp/disclaimer.txt'", build_video_filter(args, subtitle, Path("/tmp/disclaimer.txt")))

    def test_size_limit_reserves_audio_and_overhead(self):
        self.source.write_bytes(b"x" * 4_000_000)
        video_bitrate, audio_bitrate = constrained_bitrates(self.source, duration=60, multiplier=3)
        self.assertEqual(audio_bitrate, 160_000)
        self.assertGreater(video_bitrate, 1_000_000)
        self.assertLess(video_bitrate + audio_bitrate, 1_600_000)


if __name__ == "__main__":
    unittest.main()
