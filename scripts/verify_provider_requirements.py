#!/usr/bin/env python3
"""Verify the provider requirements CLI reports a usable Multipass install."""

from __future__ import annotations

import json
import subprocess
import sys


def main() -> int:
    result = subprocess.run(
        [
            "poetry",
            "-C",
            "provider-server",
            "run",
            "golem-provider",
            "requirements",
            "check",
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        return result.returncode

    data = json.loads(result.stdout)
    assert data["installed"] is True
    assert data["compatible"] is True
    assert data["daemon_running"] is True
    assert data["action_required"] == "none"
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
