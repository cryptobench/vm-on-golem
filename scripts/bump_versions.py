#!/usr/bin/env python3
"""Utility to bump patch versions in pyproject.toml files.

If the BUILD_NUMBER environment variable is provided, the patch version will
be replaced with that number. Otherwise, the patch will be incremented by one.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

PATTERN = re.compile(r'version\s*=\s*"(\d+)\.(\d+)\.(\d+)"')


def bump(text: str, build_number: int | None) -> tuple[str, bool]:
    """Return text with bumped patch version and whether a change was made."""

    def _replace(match: re.Match[str]) -> str:
        major, minor, patch = map(int, match.groups())
        if build_number is not None:
            patch = build_number if build_number > patch else patch + 1
        else:
            patch += 1
        return f'version = "{major}.{minor}.{patch}"'

    new_text, count = PATTERN.subn(_replace, text, count=1)
    return new_text, bool(count)


def process_file(path: Path, build_number: int | None) -> bool:
    text = path.read_text()
    new_text, changed = bump(text, build_number)
    if changed:
        path.write_text(new_text)
    return changed


def main() -> None:
    if len(sys.argv) > 1:
        files = [Path(p) for p in sys.argv[1:]]
    else:
        files = list(Path('.').glob('*/pyproject.toml'))

    build_num_env = os.getenv('BUILD_NUMBER')
    build_number = int(build_num_env) if build_num_env and build_num_env.isdigit() else None

    for file in files:
        if not file.exists():
            print(f"Skipping missing {file}")
            continue
        if process_file(file, build_number):
            print(f"Bumped {file}")
        else:
            print(f"No version found in {file}")


if __name__ == '__main__':
    main()
