#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DISALLOWED_PARTS = {".env", "outputs", "runtime", ".DS_Store", "__pycache__", ".pytest_cache"}
DISALLOWED_SUFFIXES = {".mp4", ".mov", ".mkv", ".zip", ".log", ".pyc"}
LOCAL_ONLY_DIRS = {".git", "local-projects"}


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def parse_frontmatter(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        fail(f"{path.relative_to(ROOT)} must start with YAML frontmatter")

    fields: dict[str, str] = {}
    for line in lines[1:]:
        if line == "---":
            return fields
        if not line.strip():
            continue
        if ":" not in line:
            fail(f"{path.relative_to(ROOT)} has invalid frontmatter line: {line}")
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip()

    fail(f"{path.relative_to(ROOT)} frontmatter is not closed")
    return fields


def validate_registry() -> list[dict]:
    registry_path = ROOT / "registry.json"
    if not registry_path.exists():
        fail("registry.json is missing")

    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    if registry.get("namespace") != "aiaaaa4":
        fail("registry namespace must be aiaaaa4")

    items = registry.get("items")
    if not isinstance(items, list) or not items:
        fail("registry.items must be a non-empty list")

    seen_ids: set[str] = set()
    seen_slugs: set[str] = set()
    for item in items:
        skill_id = item.get("skill_id")
        slug = item.get("slug")
        rel_path = item.get("path")
        kind = item.get("kind")
        if not all(isinstance(x, str) and x for x in [skill_id, slug, rel_path, kind]):
            fail(f"registry item has missing required fields: {item}")
        if skill_id in seen_ids:
            fail(f"duplicate skill_id: {skill_id}")
        if slug in seen_slugs:
            fail(f"duplicate slug: {slug}")
        seen_ids.add(skill_id)
        seen_slugs.add(slug)

        item_path = ROOT / rel_path
        if not item_path.exists():
            fail(f"registry path does not exist: {rel_path}")
        if kind == "skill" and not (item_path / "SKILL.md").exists():
            fail(f"skill is missing SKILL.md: {rel_path}")

    return items


def validate_skills(items: list[dict]) -> None:
    for item in items:
        if item["kind"] != "skill":
            continue
        path = ROOT / item["path"] / "SKILL.md"
        fields = parse_frontmatter(path)
        keys = set(fields)
        if keys != {"name", "description"}:
            fail(f"{path.relative_to(ROOT)} frontmatter keys must be exactly name and description; got {sorted(keys)}")
        if fields["name"] != item["slug"]:
            fail(f"{path.relative_to(ROOT)} name must match registry slug {item['slug']}")
        if not fields["description"]:
            fail(f"{path.relative_to(ROOT)} description is empty")


def validate_public_tree() -> None:
    for path in ROOT.rglob("*"):
        rel = path.relative_to(ROOT)
        if any(part in LOCAL_ONLY_DIRS for part in rel.parts):
            continue
        if any(part in DISALLOWED_PARTS for part in rel.parts):
            fail(f"disallowed local/generated path in repo: {rel}")
        if path.is_file() and path.suffix.lower() in DISALLOWED_SUFFIXES:
            fail(f"disallowed generated/binary file in repo: {rel}")


def main() -> None:
    items = validate_registry()
    validate_skills(items)
    validate_public_tree()
    print("repo validation passed")


if __name__ == "__main__":
    main()
