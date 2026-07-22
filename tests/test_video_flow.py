import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class VideoFlowTest(unittest.TestCase):
    def test_flow_lock_matches_component_skill_versions(self):
        result = subprocess.run(
            [sys.executable, "tools/sync_video_flow.py", "--check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("current", result.stdout)

    def test_flow_has_single_source_of_truth_and_safe_defaults(self):
        flow = json.loads((ROOT / "flows/video-flow/flow.json").read_text(encoding="utf-8"))
        self.assertEqual(flow["flow_id"], "aiaaaa4.video-flow")
        self.assertEqual(flow["display_name"], "视频素材准备工作流")
        self.assertEqual(flow["version"], "2.0.0")
        self.assertEqual(flow["path"], "flows/video-flow")
        self.assertEqual(flow["source_of_truth"], "skills/<slug>")
        self.assertEqual(set(flow["dependencies"]), {
            "aiaaaa4.video-download",
            "aiaaaa4.video-translate",
        })

    def test_flow_defaults_are_mirrored_by_component_contracts(self):
        flow = json.loads((ROOT / "flows/video-flow/flow.json").read_text(encoding="utf-8"))
        translate = (ROOT / "skills/video-translate/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("默认由 `qwen-mt-plus`", translate)
        self.assertIn("导出双语 ASS/SRT", translate)
        self.assertEqual(flow["defaults"]["subtitle_delivery"], ["ass", "srt"])


if __name__ == "__main__":
    unittest.main()
