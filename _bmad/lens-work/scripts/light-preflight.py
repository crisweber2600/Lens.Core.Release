#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# ///
"""Compatibility wrapper for stale prompt stubs that still use the legacy path."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    target = (
        Path(__file__).resolve().parent.parent
        / "skills"
        / "lens-preflight"
        / "scripts"
        / "light-preflight.py"
    )
    if not target.is_file():
        print(
            f"[LENS:PREFLIGHT] FAIL — compatibility stub could not locate canonical preflight at {target}",
            file=sys.stderr,
        )
        return 1

    result = subprocess.run([sys.executable, str(target), *sys.argv[1:]], cwd=Path.cwd())
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())