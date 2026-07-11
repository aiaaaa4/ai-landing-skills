import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "skills" / "video-publish" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from extract_covers import candidate_timestamps  # noqa: E402
from prepend_intro import build_concat_command, build_intro_command, parse_args, validate_args  # noqa: E402


class LightweightIntroTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source = self.root / "source.mp4"
        self.cover = self.root / "cover.png"
        self.disclaimer = self.root / "disclaimer.png"
        self.output = self.root / "output.mp4"
        for path in (self.source, self.cover, self.disclaimer):
            path.write_bytes(b"test")

    def tearDown(self):
        self.tmp.cleanup()

    def parse(self, *extra: str):
        argv = [
            "prepend_intro.py",
            str(self.source),
            "--cover-image",
            str(self.cover),
            "--disclaimer-image",
            str(self.disclaimer),
            "--output",
            str(self.output),
            *extra,
        ]
        with patch.object(sys, "argv", argv):
            return parse_args()

    def test_extracts_five_even_candidates_from_first_half(self):
        self.assertEqual(candidate_timestamps(120, 5, 0.5), [10, 20, 30, 40, 50])

    def test_builds_short_intro_and_stream_copy_concat(self):
        args = self.parse("--cover-seconds", "1.5", "--disclaimer-seconds", "2", "--preview-content-seconds", "8")
        source, cover, disclaimer, output = validate_args(args)
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
        intro_command = build_intro_command("ffmpeg", cover, disclaimer, self.root / "intro.mp4", media, 1.5, 2)
        self.assertIn("libx264", intro_command)
        self.assertIn("concat=n=2", " ".join(intro_command))
        concat_command = build_concat_command("ffmpeg", self.root / "concat.txt", output, 3.5, 8, False)
        self.assertIn("copy", concat_command)
        self.assertIn("11.5", concat_command)
        self.assertEqual(source, self.source.resolve())


if __name__ == "__main__":
    unittest.main()
