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
        self.assertEqual(flow["display_name"], "视频生产工作流")
        self.assertEqual(flow["path"], "flows/video-flow")
        self.assertEqual(flow["source_of_truth"], "skills/<slug>")
        self.assertEqual(flow["defaults"]["publish_covers"], False)
        self.assertEqual(flow["defaults"]["publish_subtitle_format"], "bcc")
        self.assertEqual(set(flow["dependencies"]), {
            "aiaaaa4.video-download",
            "aiaaaa4.video-translate",
            "aiaaaa4.video-publish",
        })

    def test_flow_defaults_are_mirrored_by_component_contracts(self):
        flow = json.loads((ROOT / "flows/video-flow/flow.json").read_text(encoding="utf-8"))
        translate = (ROOT / "skills/video-translate/SKILL.md").read_text(encoding="utf-8")
        publish = (ROOT / "skills/video-publish/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("默认由 `qwen-mt-plus`", translate)
        self.assertIn("导出双语 ASS/SRT", translate)
        self.assertIn(f"免责声明 `{flow['defaults']['publish_disclaimer_seconds']}` 秒", publish)
        self.assertIn("抽取 `5` 张独立投稿封面默认关闭", publish)
        self.assertIn("发布版双语 BCC", publish)


if __name__ == "__main__":
    unittest.main()
