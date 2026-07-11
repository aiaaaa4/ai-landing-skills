import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "cloud-file-mgmt" / "scripts"


class CloudFileManagementTest(unittest.TestCase):
    def test_shell_scripts_are_valid(self):
        for name in ("cloud-upload.sh", "cloud-download.sh", "cloud-delete.sh"):
            subprocess.run(["bash", "-n", str(SCRIPTS / name)], check=True)

    def test_upload_accepts_any_top_level_alist_mount(self):
        result = subprocess.run(
            [str(SCRIPTS / "cloud-upload.sh"), "onedrive", "/definitely/missing"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("Local path not found", result.stderr)
        self.assertNotIn("baidu or quark", result.stderr)

    def test_scripts_reject_nested_mount_names(self):
        commands = (
            [str(SCRIPTS / "cloud-upload.sh"), "nested/mount", "/definitely/missing"],
            [str(SCRIPTS / "cloud-download.sh"), "nested/mount", "file.txt"],
            [str(SCRIPTS / "cloud-delete.sh"), "nested/mount", "file.txt"],
        )
        for command in commands:
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn("top-level mount name", result.stderr)


if __name__ == "__main__":
    unittest.main()
