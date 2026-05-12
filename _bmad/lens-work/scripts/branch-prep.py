#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""
branch-prep.py — Thin entry-point wrapper for branch_prep.py.

All implementation lives in branch_prep.py (underscore form).  This hyphenated
alias exists so the script can be invoked via ``uv run --script branch-prep.py``
from the command line.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow importing branch_prep from the same directory even when invoked directly.
sys.path.insert(0, str(Path(__file__).parent))

from branch_prep import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
