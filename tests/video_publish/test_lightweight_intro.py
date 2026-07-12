import sys
import tempfile
import unittest
import random
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "skills" / "video-publish" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from extract_covers import candidate_timestamps  # noqa: E402
from prepend_intro import (  # noqa: E402
    build_intro_command,
    build_mux_command,
    build_source_transport_command,
    transport_offset_seconds,
    parse_args,
    validate_args,
)


class LightweightIntroTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source = self.root / "source.mp4"
        self.disclaimer = self.root / "disclaimer.png"
        self.output = self.root / "output.mp4"
        for path in (self.source, self.disclaimer):
            path.write_bytes(b"test")

    def tearDown(self):
        self.tmp.cleanup()

    def parse(self, *extra: str):
        argv = [
            "prepend_intro.py",
            str(self.source),
            "--disclaimer-image",
            str(self.disclaimer),
            "--output",
            str(self.output),
            *extra,
        ]
        with patch.object(sys, "argv", argv):
            return parse_args()

    def test_extracts_five_randomized_candidates_across_first_half(self):
        timestamps = candidate_timestamps(120, 5, 0.5, random.Random(4))
        self.assertEqual(len(timestamps), 5)
        for index, timestamp in enumerate(timestamps):
            self.assertGreaterEqual(timestamp, index * 12 + 1.2)
            self.assertLessEqual(timestamp, (index + 1) * 12 - 1.2)

    def test_builds_short_intro_and_stream_copy_concat(self):
        args = self.parse("--disclaimer-seconds", "3", "--preview-content-seconds", "8")
        source, disclaimer, output, subtitle, timeline_output, subtitle_output = validate_args(args)
        media = {
            "video": {
                "width": 1920,
                "height": 1080,
                "r_frame_rate": "25/1",
                "time_base": "1/12800",
                "level": 40,
            },
            "audio": {"sample_rate": "44100", "channels": 2, "channel_layout": "stereo", "bit_rate": "128000"},
        }
        intro_command = build_intro_command("ffmpeg", disclaimer, self.root / "intro.ts", media, 3)
        self.assertIn("libx264", intro_command)
        self.assertIn("mpegts", intro_command)
        self.assertIn("ref=3:b-pyramid=none", " ".join(intro_command))
        self.assertIn("chroma-qp-offset=0", " ".join(intro_command))
        source_command = build_source_transport_command("ffmpeg", source, media, 3, 8)
        self.assertIn("copy", source_command)
        self.assertIn("h264_mp4toannexb", source_command)
        self.assertIn("8", source_command)
        mux_command = build_mux_command("ffmpeg", output, False)
        self.assertIn("aac_adtstoasc", mux_command)
        self.assertIn("+faststart", mux_command)
        self.assertEqual(source, self.source.resolve())
        self.assertIsNone(subtitle)
        self.assertIsNone(subtitle_output)
        self.assertEqual(timeline_output, self.output.with_suffix(".timeline.json").resolve())

    def test_calculates_transport_offset_from_actual_frame_rate(self):
        media = {"video": {"r_frame_rate": "25/1"}}
        self.assertAlmostEqual(transport_offset_seconds(media, 3), 3.080011111, places=8)

    def test_derives_and_shifts_release_subtitle(self):
        subtitle = self.root / "source.中英双语字幕.srt"
        subtitle.write_text(
            "1\n00:00:01,950 --> 00:00:03,100\n中文\nEnglish\n",
            encoding="utf-8",
        )
        args = self.parse("--subtitle", str(subtitle))
        source, _, output, resolved_subtitle, _, subtitle_output = validate_args(args)
        self.assertEqual(resolved_subtitle, subtitle.resolve())
        self.assertEqual(subtitle_output, (self.root / "output.中英双语字幕.srt").resolve())

        from subtitle_timeline import shift_srt_file

        shift_srt_file(resolved_subtitle, subtitle_output, 3.080011111)
        shifted = subtitle_output.read_text(encoding="utf-8")
        self.assertIn("00:00:05,030 --> 00:00:06,180", shifted)
        self.assertIn("中文\nEnglish", shifted)
        self.assertIn(b"\r\n", subtitle_output.read_bytes())

    def test_defaults_to_three_second_disclaimer(self):
        self.assertEqual(self.parse().disclaimer_seconds, 3.0)

    def test_refuses_to_overwrite_source_subtitle(self):
        subtitle = self.root / "source.srt"
        subtitle.write_text("1\n00:00:00,000 --> 00:00:01,000\nText\n", encoding="utf-8")
        args = self.parse(
            "--subtitle",
            str(subtitle),
            "--subtitle-output",
            str(subtitle),
            "--overwrite",
        )
        with self.assertRaisesRegex(RuntimeError, "distinct paths"):
            validate_args(args)


if __name__ == "__main__":
    unittest.main()
