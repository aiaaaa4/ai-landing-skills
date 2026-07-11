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
        source, disclaimer, output = validate_args(args)
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

    def test_defaults_to_three_second_disclaimer(self):
        self.assertEqual(self.parse().disclaimer_seconds, 3.0)


if __name__ == "__main__":
    unittest.main()
