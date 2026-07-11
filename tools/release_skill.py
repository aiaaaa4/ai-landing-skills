#!/usr/bin/env python3
"""Publish exactly one registry-managed skill to ClawHub."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def run(command: list[str], *, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, check=True, text=True, capture_output=capture_output)
    except subprocess.CalledProcessError as error:
        if error.stdout:
            print(error.stdout, end="")
        if error.stderr:
            print(error.stderr, end="", file=sys.stderr)
        fail(f"command failed: {' '.join(command[:3])}")


def load_registry() -> tuple[dict, dict]:
    registry = json.loads((ROOT / "registry.json").read_text(encoding="utf-8"))
    repository = registry.get("repository")
    if not isinstance(repository, dict):
        fail("registry.repository is missing")
    return registry, repository


def select_skill(registry: dict, slug: str) -> dict:
    for item in registry.get("items", []):
        if item.get("slug") == slug and item.get("kind") == "skill":
            return item
    fail(f"unknown public skill: {slug}")
    return {}


def source_commit() -> str:
    result = run(["git", "rev-parse", "HEAD"], capture_output=True)
    return result.stdout.strip()


def authenticate() -> None:
    token = os.environ.get("CLAWHUB_TOKEN")
    if not token:
        return
    run(["npx", "--yes", "clawhub@latest", "login", "--token", token, "--label", "GitHub Actions"])


def publish_command(item: dict, repository: dict, changelog: str, dry_run: bool) -> list[str]:
    clawhub = item["clawhub"]
    publish_slug = clawhub.get("slug", item["slug"])
    command = [
        "npx",
        "--yes",
        "clawhub@latest",
        "skill",
        "publish",
        item["path"],
        "--owner",
        repository["owner"],
        "--slug",
        publish_slug,
        "--name",
        item["display_name"],
        "--version",
        item["version"],
        "--changelog",
        changelog,
        "--source-repo",
        f"{repository['owner']}/{repository['name']}",
        "--source-ref",
        repository["branch"],
        "--source-commit",
        source_commit(),
        "--source-path",
        item["path"],
        "--topics",
        ",".join(clawhub["topics"]),
        "--json",
    ]
    if dry_run:
        command.append("--dry-run")
    return command


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill", required=True, help="Registry slug to publish")
    parser.add_argument("--changelog", required=True, help="Public release summary")
    parser.add_argument("--dry-run", action="store_true", help="Validate with ClawHub without publishing")
    args = parser.parse_args()

    if not args.changelog.strip():
        fail("changelog must not be empty")

    validation = run([sys.executable, "tools/validate_repo.py"], capture_output=True)
    print(validation.stdout, end="")

    registry, repository = load_registry()
    item = select_skill(registry, args.skill)
    authenticate()
    command = publish_command(item, repository, args.changelog.strip(), args.dry_run)
    run(command)


if __name__ == "__main__":
    main()
