from __future__ import annotations

import importlib.util
import contextlib
import io
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("release_skill", ROOT / "tools" / "release_skill.py")
assert SPEC and SPEC.loader
release_skill = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release_skill)


class ReleaseSkillTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry, self.repository = release_skill.load_registry()

    def test_registry_exposes_all_public_skills(self) -> None:
        slugs = {item["slug"] for item in self.registry["items"]}
        self.assertEqual(slugs, {"video-download", "video-translate", "video-publish"})
        expected_platforms = {"github", "clawhub", "skills.sh", "skillhub", "skillsmp"}
        for item in self.registry["items"]:
            self.assertEqual(set(item["platforms"]), expected_platforms)

    def test_publish_command_uses_registry_metadata(self) -> None:
        item = release_skill.select_skill(self.registry, "video-download")
        command = release_skill.publish_command(item, self.repository, "Test release", dry_run=True)
        self.assertIn("一键加速视频下载", command)
        self.assertIn(item["version"], command)
        self.assertIn("video,download,yt-dlp,aiaaaa4", command)
        self.assertIn("--dry-run", command)

    def test_publish_command_keeps_canonical_slug(self) -> None:
        item = release_skill.select_skill(self.registry, "video-translate")
        command = release_skill.publish_command(item, self.repository, "Canonical release", dry_run=True)
        slug_index = command.index("--slug") + 1
        self.assertEqual(command[slug_index], "video-translate")

    def test_semver_order_matches_release_policy(self) -> None:
        self.assertLess(release_skill.semver_key("1.0.9"), release_skill.semver_key("1.1.0"))
        self.assertLess(release_skill.semver_key("1.1.9"), release_skill.semver_key("1.2.0"))

    def test_existing_version_cannot_be_republished(self) -> None:
        item = release_skill.select_skill(self.registry, "video-download")
        published = {"latestVersion": {"version": item["version"]}}
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                release_skill.ensure_newer_version(item, published)

    def test_read_back_verifies_canonical_identity(self) -> None:
        item = release_skill.select_skill(self.registry, "video-download")
        published = {
            "skill": {"slug": item["slug"], "displayName": item["display_name"]},
            "latestVersion": {"version": item["version"]},
            "owner": {"handle": self.repository["owner"]},
            "moderation": {
                "isSuspicious": False,
                "isMalwareBlocked": False,
                "verdict": "clean",
            },
        }
        with contextlib.redirect_stdout(io.StringIO()):
            release_skill.verify_published_skill(item, self.repository, published)


if __name__ == "__main__":
    unittest.main()
