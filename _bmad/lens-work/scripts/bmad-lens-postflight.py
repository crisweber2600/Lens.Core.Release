#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""
bmad-lens-postflight.py — Lens session postflight closeout.

Inspects the three standard Lens repos (control, governance, target), automatically
commits and pushes local session changes when safe, then verifies clean state.

Usage (from workspace root):
    uv run lens.core/_bmad/lens-work/scripts/bmad-lens-postflight.py
    uv run lens.core/_bmad/lens-work/scripts/bmad-lens-postflight.py --format json
    uv run lens.core/_bmad/lens-work/scripts/bmad-lens-postflight.py --target-repo path/to/repo
    uv run lens.core/_bmad/lens-work/scripts/bmad-lens-postflight.py --verify-only

Options:
    --workspace-root PATH   Explicit workspace root; auto-detected from cwd if omitted.
    --target-repo PATH      Override the default target repo path.
    --format text|json      Output format (default: text).
    --verify-only           Do not commit/push; only report repository state.

Exit codes:
  0 — all repos clean or auto-closeout succeeded
  1 — one or more repos are still dirty, closeout failed, or workspace root not found
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


AUTO_COMMIT_MESSAGE = "chore(postflight): auto-closeout session changes"


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


def git_current_branch(repo_path: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return ""
    branch = result.stdout.strip()
    return "" if branch == "HEAD" else branch


def git_commit_all(repo_path: Path, message: str) -> tuple[bool, str]:
    add_result = subprocess.run(
        ["git", "add", "-A"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=False,
    )
    if add_result.returncode != 0:
        return False, add_result.stderr.strip() or "git add failed"

    commit_result = subprocess.run(
        ["git", "commit", "-m", message],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=False,
    )
    if commit_result.returncode != 0:
        stderr = commit_result.stderr.strip()
        stdout = commit_result.stdout.strip()
        if "nothing to commit" in (stderr + "\n" + stdout).lower():
            return True, "nothing_to_commit"
        return False, stderr or stdout or "git commit failed"

    sha = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=False,
    )
    return True, sha.stdout.strip() if sha.returncode == 0 else ""


def git_push_current_branch(repo_path: Path) -> tuple[bool, str]:
    branch = git_current_branch(repo_path)
    if not branch:
        return False, "detached_head_or_branch_unknown"

    push_result = subprocess.run(
        ["git", "push", "-u", "origin", branch],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=False,
    )
    if push_result.returncode != 0:
        return False, push_result.stderr.strip() or push_result.stdout.strip() or "git push failed"
    return True, branch


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
            "auto_commit": None,
            "auto_push": None,
            "auto_error": None,
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
        "auto_commit": None,
        "auto_push": None,
        "auto_error": None,
    }


def auto_close_repo(repo_state: dict) -> dict:
    if not repo_state.get("exists") or not repo_state.get("dirty"):
        return repo_state

    repo_path = Path(repo_state["path"])
    uncommitted = repo_state.get("uncommitted", [])

    if uncommitted:
        ok, commit_info = git_commit_all(repo_path, AUTO_COMMIT_MESSAGE)
        if not ok:
            repo_state["auto_error"] = f"commit_failed: {commit_info}"
            return repo_state
        if commit_info != "nothing_to_commit":
            repo_state["auto_commit"] = commit_info

    ok_push, push_info = git_push_current_branch(repo_path)
    if not ok_push:
        repo_state["auto_error"] = f"push_failed: {push_info}"
        return repo_state
    repo_state["auto_push"] = push_info

    repo_state["uncommitted"] = git_status_lines(repo_path)
    repo_state["unpushed"] = git_unpushed_commits(repo_path)
    repo_state["dirty"] = bool(repo_state["uncommitted"]) or bool(repo_state["unpushed"])
    return repo_state


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
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify state; do not auto-commit or auto-push dirty repos.",
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


def print_text_report(results: list[dict], any_dirty: bool, verify_only: bool) -> None:
    mode = "verification" if verify_only else "auto-closeout"
    print(f"[LENS:POSTFLIGHT] Verifying workspace repos ({mode})...")
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
            if r.get("auto_error"):
                print(f"                 [auto-closeout-error] {r['auto_error']}")
        else:
            print(f"  {r['label']:12s}  clean [OK]")
            if r.get("auto_commit"):
                print(f"                 [auto-commit] {r['auto_commit']}")
            if r.get("auto_push"):
                print(f"                 [auto-push] {r['auto_push']}")

    if any_dirty:
        print(
            "\n[LENS:POSTFLIGHT] FAIL - one or more repos still have uncommitted or unpushed changes."
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

    if not args.verify_only:
        results = [auto_close_repo(r) for r in results]

    any_dirty = any(r["dirty"] for r in results)

    if args.format == "json":
        output = {
            "status": "dirty" if any_dirty else "clean",
            "mode": "verify-only" if args.verify_only else "auto-closeout",
            "repos": results,
        }
        print(json.dumps(output, indent=2))
    else:
        print_text_report(results, any_dirty, args.verify_only)

    return 1 if any_dirty else 0


if __name__ == "__main__":
    raise SystemExit(main())
