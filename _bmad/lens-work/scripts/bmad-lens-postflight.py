#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""
bmad-lens-postflight.py — Lens session postflight verifier.

Inspects the three standard Lens repos (control, governance, target) for uncommitted
or unpushed changes. Exits 0 when all repos are clean, 1 when any repo is dirty.

Usage (from workspace root):
    uv run lens.core/_bmad/lens-work/scripts/bmad-lens-postflight.py
    uv run lens.core/_bmad/lens-work/scripts/bmad-lens-postflight.py --format json
    uv run lens.core/_bmad/lens-work/scripts/bmad-lens-postflight.py --target-repo path/to/repo

Options:
    --workspace-root PATH   Explicit workspace root; auto-detected from cwd if omitted.
    --target-repo PATH      Override the default target repo path.
    --format text|json      Output format (default: text).

Exit codes:
  0 — all repos clean
  1 — one or more repos are dirty, or workspace root not found
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Workspace root detection
# ---------------------------------------------------------------------------

def find_workspace_root() -> Path | None:
    """Walk up from cwd to find the canonical Lens workspace root."""
    current = Path.cwd().resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "lens.core" / "_bmad" / "lens-work" / "lifecycle.yaml").is_file():
            return candidate
        if (candidate / "_bmad" / "lens-work" / "lifecycle.yaml").is_file():
            return candidate
    return None


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def git_status_lines(repo_path: Path) -> list[str]:
    """Return non-empty lines from `git status --short`, or error lines.

    Returns [] (not dirty) when the directory is not a git repository so that
    non-git workspace-root directories are treated as SKIP rather than dirty.
    """
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            # "not a git repository" is not an error — treat as skip (not dirty)
            if "not a git repository" in stderr.lower():
                return []
            return [f"[ERROR] git status failed: {stderr}"]
        return [ln for ln in result.stdout.splitlines() if ln.strip()]
    except FileNotFoundError:
        return ["[ERROR] git not found in PATH"]


def git_unpushed_commits(repo_path: Path) -> list[str]:
    """Return log lines for commits not yet pushed to the remote tracking branch."""
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "@{u}..HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            # No upstream configured — not an error for postflight
            return []
        return [ln for ln in result.stdout.splitlines() if ln.strip()]
    except FileNotFoundError:
        return []


# ---------------------------------------------------------------------------
# Repo check
# ---------------------------------------------------------------------------

def check_repo(label: str, path: Path) -> dict:
    if not path.is_dir():
        return {
            "label": label,
            "path": str(path),
            "exists": False,
            "dirty": False,
            "uncommitted": [],
            "unpushed": [],
        }
    uncommitted = git_status_lines(path)
    unpushed = git_unpushed_commits(path)
    dirty = bool(uncommitted) or bool(unpushed)
    return {
        "label": label,
        "path": str(path),
        "exists": True,
        "dirty": dirty,
        "uncommitted": uncommitted,
        "unpushed": unpushed,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Lens session postflight — verifies all repos are clean."
    )
    parser.add_argument(
        "--workspace-root",
        default="",
        help="Explicit workspace root path. Auto-detected from cwd if omitted.",
    )
    parser.add_argument(
        "--target-repo",
        default="",
        help="Path to the target repo. Defaults to TargetProjects/lens-dev/new-codebase/lens.core.src.",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format (default: text).",
    )
    return parser


def resolve_paths(args: argparse.Namespace) -> tuple[Path, Path, Path]:
    if args.workspace_root:
        root = Path(args.workspace_root).resolve()
    else:
        root = find_workspace_root()
        if root is None:
            print(
                "[LENS:POSTFLIGHT] FAIL — cannot locate workspace root "
                "(lens.core/_bmad/lens-work/lifecycle.yaml not found from cwd).",
                file=sys.stderr,
            )
            raise SystemExit(1)

    governance_repo = root / "TargetProjects" / "lens" / "lens-governance"

    if args.target_repo:
        raw = Path(args.target_repo)
        target_repo = raw.resolve() if not raw.is_absolute() else raw
    else:
        target_repo = root / "TargetProjects" / "lens-dev" / "new-codebase" / "lens.core.src"

    return root, governance_repo, target_repo


def print_text_report(results: list[dict], any_dirty: bool) -> None:
    print("[LENS:POSTFLIGHT] Verifying workspace repos...")
    for r in results:
        if not r["exists"]:
            print(f"  {r['label']:12s}  SKIP  (not found: {r['path']})")
            continue
        if r["dirty"]:
            print(f"  {r['label']:12s}  DIRTY")
            for line in r["uncommitted"]:
                print(f"                 {line}")
            for line in r["unpushed"]:
                print(f"                 [unpushed] {line}")
        else:
            print(f"  {r['label']:12s}  clean [OK]")

    if any_dirty:
        print(
            "\n[LENS:POSTFLIGHT] FAIL - one or more repos have uncommitted or unpushed changes."
            "\nCommit and push all changes before ending the session."
        )
    else:
        print("\n[LENS:POSTFLIGHT] OK - all repos verified clean [OK]")


def main() -> int:
    args = build_parser().parse_args()
    root, governance_repo, target_repo = resolve_paths(args)

    results = [
        check_repo("control", root),
        check_repo("governance", governance_repo),
        check_repo("target", target_repo),
    ]

    any_dirty = any(r["dirty"] for r in results)

    if args.format == "json":
        output = {
            "status": "dirty" if any_dirty else "clean",
            "repos": results,
        }
        print(json.dumps(output, indent=2))
    else:
        print_text_report(results, any_dirty)

    return 1 if any_dirty else 0


if __name__ == "__main__":
    raise SystemExit(main())
