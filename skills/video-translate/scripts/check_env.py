#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


REQUIRED_ENV = ("DASHSCOPE_API_KEY", "ALIYUN_WORKSPACE_ID", "OKFILE_TOKEN")

ENV_SETUP_HINTS = {
    "DASHSCOPE_API_KEY": (
        "Sign in to Alibaba Model Studio at https://bailian.console.aliyun.com/, create a DashScope "
        "API key, and add a small balance (2-10 CNY) before batch use."
    ),
    "ALIYUN_WORKSPACE_ID": (
        "Copy the workspace ID from the Alibaba Model Studio console (https://bailian.console.aliyun.com/)."
    ),
    "OKFILE_TOKEN": (
        "Register at https://www.okfile.com/ and create/copy the API key from "
        "https://www.okfile.com/en/account/api-keys."
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check the video subtitle workflow environment.")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--json", action="store_true", help="Print a machine-readable JSON result for automation runners.")
    return parser.parse_args()


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def has_real_value(value: str | None) -> bool:
    if not value:
        return False
    stripped = value.strip()
    return stripped != "..." and not stripped.startswith("填写")


def check_python(errors: list[str]) -> None:
    version = sys.version_info
    print(f"Python: {platform.python_version()} ({sys.executable})")
    if version < (3, 9):
        errors.append("[VTZ-E001] Python 3.9+ is required.")


def check_ffmpeg(errors: list[str]) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        errors.append("[VTZ-E002] ffmpeg was not found on PATH.")
        system = platform.system().lower()
        if system == "windows":
            print("Install hint: winget install Gyan.FFmpeg")
        elif system == "darwin":
            print("Install hint: brew install ffmpeg")
        else:
            print("Install hint: use your package manager, for example apt install ffmpeg")
        return

    result = subprocess.run([ffmpeg, "-version"], check=False, capture_output=True, text=True)
    first_line = result.stdout.splitlines()[0] if result.stdout else ffmpeg
    print(f"ffmpeg: {first_line}")


def check_env_values(errors: list[str]) -> None:
    for key in REQUIRED_ENV:
        if has_real_value(os.environ.get(key)):
            print(f"{key}: set")
        else:
            hint = ENV_SETUP_HINTS.get(key, "")
            message = f"[VTZ-E001] {key} is missing or still a placeholder."
            if hint:
                message = f"{message} {hint}"
            errors.append(message)

    region = os.environ.get("ALIYUN_REGION") or "cn-beijing"
    print(f"ALIYUN_REGION: {region}")


def main() -> int:
    args = parse_args()
    load_env(args.env_file)

    errors: list[str] = []
    print(f"OS: {platform.system()} {platform.release()} ({platform.machine()})")
    check_python(errors)
    check_ffmpeg(errors)
    check_env_values(errors)
    if args.json:
        result = {
            "ok": not errors,
            "python": platform.python_version(),
            "ffmpeg": bool(shutil.which("ffmpeg")),
            "env": {key: has_real_value(os.environ.get(key)) for key in REQUIRED_ENV},
            "env_file": str(args.env_file),
            "errors": errors,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if not errors else 1

    if errors:
        print("\nEnvironment check failed:")
        for error in errors:
            print(f"- {error}")
        print("\nCreate/update the local .env file next to the scripts folder; see SKILL.md or README.md for the template.")
        return 1

    print("\nEnvironment check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
