#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# ///
"""Frozen preflight gate for prompt stubs.

Exit 0 -> proceed.
Exit 1 -> halt.
"""

from __future__ import annotations

import sys
from pathlib import Path


def find_project_root() -> Path | None:
    current = Path.cwd().resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "_bmad").is_dir():
            return candidate
    return None


def check_python_version() -> tuple[bool, str]:
    major, minor = sys.version_info.major, sys.version_info.minor
    if (major, minor) >= (3, 12):
        return True, f"Python {major}.{minor}"
    return False, f"Python {major}.{minor} — requires >= 3.12"


def main() -> int:
    root = find_project_root()
    if root is None:
        print("[LENS:PREFLIGHT] FAIL — could not locate project root (_bmad not found)", file=sys.stderr)
        return 1

    ok_python, msg = check_python_version()
    if not ok_python:
        print(f"[LENS:PREFLIGHT] FAIL — {msg}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
