#!/usr/bin/env python3
"""Keep the composite video Flow's dependency lock aligned with registry.json."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FLOW_PATH = ROOT / "flows/video-production/flow.json"
REQUIRED_SLUGS = ("video-download", "video-translate", "video-publish")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def expected_dependencies() -> dict[str, dict[str, str]]:
    registry = load_json(ROOT / "registry.json")
    items = {item["slug"]: item for item in registry["items"] if item.get("kind") == "skill"}
    missing = [slug for slug in REQUIRED_SLUGS if slug not in items]
    if missing:
        raise SystemExit(f"registry is missing Flow dependencies: {', '.join(missing)}")
    return {
        f"aiaaaa4.{slug}": {"path": items[slug]["path"], "version": items[slug]["version"]}
        for slug in REQUIRED_SLUGS
    }


def sync(write: bool) -> bool:
    flow = load_json(FLOW_PATH)
    expected = expected_dependencies()
    actual = flow.get("dependencies")
    if actual == expected:
        return False
    if not write:
        raise SystemExit(
            "video Flow dependency lock is stale. Run `python3 tools/sync_video_flow.py --write` "
            "after changing a component Skill version."
        )
    flow["dependencies"] = expected
    FLOW_PATH.write_text(json.dumps(flow, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="Update flow.json from registry.json.")
    parser.add_argument("--check", action="store_true", help="Verify flow.json against registry.json.")
    args = parser.parse_args()
    if args.write and args.check:
        parser.error("choose only one of --write or --check")
    changed = sync(args.write)
    print("video Flow dependency lock updated" if changed else "video Flow dependency lock is current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
