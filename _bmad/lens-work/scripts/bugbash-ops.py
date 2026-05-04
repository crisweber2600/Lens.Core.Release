#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""
bugbash-ops.py — Main entry orchestration and status summary for lens-bugbash.

Commands:
  status-summary      --governance-repo PATH

Exit codes: 0=success, 1=validation/not-found error, 2=scope violation
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from bugbash_scope_guard import assert_governance_repo_exists

try:
    import yaml
except ImportError:
    print(
        "ERROR: pyyaml is required but not installed. "
        "Run via: uv run --script bugbash-ops.py",
        file=sys.stderr,
    )
    sys.exit(1)


def _parse_frontmatter_status(content: str) -> str:
    """Extract the 'status' field from YAML frontmatter; return '' on failure."""
    if not content.startswith("---"):
        return ""
    end = content.find("\n---", 3)
    if end == -1:
        return ""
    fm_text = content[3:end]
    try:
        fm = yaml.safe_load(fm_text) or {}
        return str(fm.get("status", "")).strip('"')
    except yaml.YAMLError:
        return ""


def _count_dir(directory: Path) -> int:
    """Count *.md files in a directory; return 0 if the directory doesn't exist."""
    if not directory.exists():
        return 0
    return sum(1 for _ in directory.glob("*.md"))


def cmd_status_summary(args: argparse.Namespace) -> int:
    governance_repo = Path(args.governance_repo).resolve()
    assert_governance_repo_exists(governance_repo)

    new_count = _count_dir(governance_repo / "bugs" / "New")
    quickdev_count = _count_dir(governance_repo / "bugs" / "QuickDev")
    inprogress_count = _count_dir(governance_repo / "bugs" / "Inprogress")
    fixed_count = _count_dir(governance_repo / "bugs" / "Fixed")

    summary = {
        "New": new_count,
        "QuickDev": quickdev_count,
        "Inprogress": inprogress_count,
        "Fixed": fixed_count,
        "Total": new_count + quickdev_count + inprogress_count + fixed_count,
    }
    print(json.dumps(summary))
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bugbash-ops.py",
        description="Main entry orchestration and status summary for lens-bugbash.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    ss = sub.add_parser("status-summary", help="Print bug counts by status folder.")
    ss.add_argument("--governance-repo", required=True)

    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    dispatch = {
        "status-summary": cmd_status_summary,
    }
    fn = dispatch.get(args.command)
    if fn:
        return fn(args)
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
