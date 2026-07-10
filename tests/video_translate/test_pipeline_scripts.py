import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORK_DIR = ROOT / "skills" / "video-translate"
SCRIPTS_DIR = WORK_DIR / "scripts"
EXAMPLES_DIR = Path(__file__).resolve().parent / "fixtures"


def run_script(name: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / name), *args],
        capture_output=True,
        text=True,
        cwd=WORK_DIR,
    )


class PipelineScriptsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def build_aligned(self) -> Path:
        out_dir = self.tmp_dir / "work"
        result = run_script(
            "extract_word_stream.py",
            str(EXAMPLES_DIR / "transcript_words.json"),
            "--out-dir",
            str(out_dir),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        aligned = out_dir / "aligned_segments.json"
        result = run_script(
            "align_segments.py",
            str(out_dir / "word_table.json"),
            str(EXAMPLES_DIR / "segments.txt"),
            "--out",
            str(aligned),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return aligned

    def test_validate_example_segments(self):
        out_dir = self.tmp_dir / "work"
        run_script(
            "extract_word_stream.py",
            str(EXAMPLES_DIR / "transcript_words.json"),
            "--out-dir",
            str(out_dir),
        )
        result = run_script(
            "validate_segments.py",
            str(out_dir / "word_table.json"),
            str(EXAMPLES_DIR / "segments.txt"),
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Full word coverage: yes", result.stdout)

    def test_export_subtitles_shapes(self):
        aligned = self.build_aligned()
        out_dir = self.tmp_dir / "subtitles"
        result = run_script(
            "export_subtitles.py",
            str(aligned),
            "--out-dir",
            str(out_dir),
            "--basename",
            "example.zh-en",
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        srt = (out_dir / "example.zh-en.srt").read_text(encoding="utf-8")
        self.assertIn("00:00:00,000 -->", srt)
        self.assertIn("如果价格突破前一日高点", srt)
        # Soft trailing punctuation must be stripped in display text.
        self.assertNotIn("追涨。", srt)

        ass = (out_dir / "example.zh-en.ass").read_text(encoding="utf-8")
        self.assertIn("Style: Default,Arial,42,", ass)
        for line in ass.splitlines():
            if line.startswith("Dialogue:"):
                self.assertIn(r"{\fs42}", line)
                self.assertIn(r"{\fs24}", line)
        # Chinese first by default: fs42 tag precedes fs24 within each event.
        first_dialogue = next(line for line in ass.splitlines() if line.startswith("Dialogue:"))
        self.assertLess(first_dialogue.index(r"{\fs42}"), first_dialogue.index(r"{\fs24}"))

    def test_repair_terms(self):
        segments = self.tmp_dir / "segments.txt"
        segments.write_text(
            "[SEG 0001]\n"
            "SRC_RAW: welcome to trade pro academy on trading view\n"
            "SRC_DISPLAY: Welcome to Trade Pro Academy on Trading View.\n"
            "ZH: 欢迎来到 Trade Pro Academy，这里有黄牛、剥头皮交易员党和越狱的业绩。\n"
            "[/SEG]\n",
            encoding="utf-8",
        )
        result = run_script("repair_segments_terms.py", str(segments))
        self.assertEqual(result.returncode, 0, result.stderr)
        repaired = segments.read_text(encoding="utf-8")
        self.assertIn("TradePro Academy on TradingView", repaired)
        self.assertIn("剥头皮交易员", repaired)
        self.assertNotIn("剥头皮交易员党", repaired)
        self.assertIn("突破", repaired)
        self.assertNotIn("越狱", repaired)
        self.assertIn("交易表现", repaired)
        # SRC_RAW must stay untouched.
        self.assertIn("SRC_RAW: welcome to trade pro academy on trading view", repaired)

    def test_final_qa_clean_example(self):
        aligned = self.build_aligned()
        report = self.tmp_dir / "report.md"
        prompt = self.tmp_dir / "prompt.txt"
        result = run_script(
            "final_qa.py",
            str(aligned),
            str(EXAMPLES_DIR / "segments.txt"),
            "--out-report",
            str(report),
            "--out-prompt",
            str(prompt),
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("blockers=0", result.stdout)

    def test_final_qa_flags_coverage_gap(self):
        aligned_path = self.build_aligned()
        payload = json.loads(aligned_path.read_text(encoding="utf-8"))
        dropped = payload["segments"].pop(1)
        gapped = self.tmp_dir / "gapped.json"
        gapped.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        result = run_script(
            "final_qa.py",
            str(gapped),
            str(EXAMPLES_DIR / "segments.txt"),
            "--out-report",
            str(self.tmp_dir / "r.md"),
            "--out-prompt",
            str(self.tmp_dir / "p.txt"),
        )
        self.assertEqual(result.returncode, 1, result.stdout)
        report = (self.tmp_dir / "r.md").read_text(encoding="utf-8")
        self.assertIn("word_coverage_gap", report)
        self.assertIn(dropped["source_raw"].split()[0], report.lower())


if __name__ == "__main__":
    unittest.main()
