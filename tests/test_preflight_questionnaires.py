import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def output(path: Path, *args: str) -> str:
    result = subprocess.run([sys.executable, str(path), *args], capture_output=True, text=True, check=True)
    return result.stdout.strip()


class PreflightQuestionnaireTest(unittest.TestCase):
    def test_translate_questionnaire_separates_target_from_bilingual_output(self):
        text = output(ROOT / "skills/video-translate/scripts/preflight.py")
        self.assertIn("默认翻译为简体中文", text)
        self.assertIn("固定输出中文在上、原文在下的双语 ASS 和 SRT", text)
        self.assertIn("qwen-mt-plus", text)
        self.assertIn("Agent 大模型翻译", text)
        self.assertIn("视频翻译工作流说明书", text)
        self.assertIn("GPT-5.6", text)
        self.assertIn("https://www.okfile.com/en/account/api-keys", text)
        self.assertIn("https://help.aliyun.com/zh/model-studio/get-api-key", text)
        self.assertNotIn("简体中文、繁体中文还是双语", text)

    def test_combined_questionnaire_collects_material_preparation_once(self):
        text = output(ROOT / "skills/video-download/scripts/preflight.py", "--mode", "combined")
        self.assertIn("下载质量", text)
        self.assertIn("翻译目标与交付", text)
        self.assertIn("翻译模型", text)
        self.assertIn("Agent 大模型翻译", text)
        self.assertIn("视频下载 → 字幕翻译", text)
        self.assertNotIn("11. 发布封装", text)
        self.assertNotIn("发布版双语 BCC", text)
        self.assertIn("确认默认设置，并同意外发处理", text)

if __name__ == "__main__":
    unittest.main()
