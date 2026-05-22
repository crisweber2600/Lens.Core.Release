#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""
branch_prep.py — Target-repo branch preparation for the Lens Dev conductor.

Determines a working branch name from the provided CLI arguments and prepares
that branch in the target repository. The script checks whether the branch
exists locally or on the remote, creates it from the base branch when needed,
and reports the result as YAML. In dry-run mode, git commands are printed
instead of executed.

Strategies:
  flat              → branch name == base_branch (no new branch; work directly)
  feature-stub      → feature/{featureStub}
  feature-user      → feature/{featureStub}-{username}

Usage:
  uv run --script branch_prep.py \\
    --target-repo <path> \\
    --feature-id <id> \\
    --strategy <flat|feature-stub|feature-user> \\
    --base-branch <branch> \\
    [--username <username>] \\
    [--dry-run]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Branch name resolution
# ---------------------------------------------------------------------------

VALID_STRATEGIES = ("flat", "feature-stub", "feature-user")


def resolve_branch_name(strategy: str, feature_id: str, base_branch: str, username: str = "") -> str:
    """Return the working branch name for the given strategy."""
    if strategy == "flat":
        return base_branch
    # Extract feature stub: last segment of feature_id (e.g. lens-dev-new-codebase-dogfood → dogfood)
    feature_stub = feature_id.split("-")[-1] if "-" in feature_id else feature_id
    if strategy == "feature-stub":
        return f"feature/{feature_stub}"
    if strategy == "feature-user":
        if not username:
            raise ValueError("strategy 'feature-user' requires --username")
        return f"feature/{feature_stub}-{username}"
    raise ValueError(f"Unknown strategy: {strategy!r}. Valid values: {VALID_STRATEGIES}")


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def _run(cmd: list[str], cwd: Path, dry_run: bool = False) -> subprocess.CompletedProcess:
    """Run a git command; in dry-run mode just print it."""
    if dry_run:
        print(f"[dry-run] {' '.join(cmd)}")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)


def branch_exists_remote(repo: Path, branch: str) -> bool:
    """Return True if the branch exists on the remote."""
    result = subprocess.run(
        ["git", "ls-remote", "--heads", "origin", branch],
        capture_output=True,
        text=True,
        cwd=repo,
    )
    return bool(result.stdout.strip())


def branch_exists_local(repo: Path, branch: str) -> bool:
    """Return True if the branch exists locally."""
    result = subprocess.run(
        ["git", "branch", "--list", branch],
        capture_output=True,
        text=True,
        cwd=repo,
    )
    return bool(result.stdout.strip())


def current_branch(repo: Path) -> str:
    """Return the current branch name."""
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        cwd=repo,
    )
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# Main preparation logic
# ---------------------------------------------------------------------------

def prepare_branch(
    target_repo: Path,
    feature_id: str,
    strategy: str,
    base_branch: str,
    username: str = "",
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Idempotent branch preparation.

    Returns a result dict:
      {
        "branch": <resolved branch name>,
        "action": "created" | "resumed" | "flat",
        "errors": [<str>],
      }
    """
    errors: list[str] = []

    branch = resolve_branch_name(strategy, feature_id, base_branch, username)

    if strategy == "flat":
        # Flat strategy: ensure we are on base_branch
        cb = current_branch(target_repo)
        if cb != base_branch and not dry_run:
            _run(["git", "checkout", base_branch], cwd=target_repo, dry_run=dry_run)
        return {"branch": branch, "action": "flat", "errors": errors}

    # Feature-stub or feature-user strategy
    local_exists = branch_exists_local(target_repo, branch)
    remote_exists = branch_exists_remote(target_repo, branch)

    if local_exists:
        # Resume: checkout and pull if remote exists
        _run(["git", "checkout", branch], cwd=target_repo, dry_run=dry_run)
        if remote_exists:
            r = _run(["git", "pull", "--ff-only", "origin", branch], cwd=target_repo, dry_run=dry_run)
            if r.returncode != 0 and not dry_run:
                errors.append(f"Pull failed: {r.stderr.strip()}")
        return {"branch": branch, "action": "resumed", "errors": errors}

    # Create branch from base
    _run(["git", "checkout", base_branch], cwd=target_repo, dry_run=dry_run)
    _run(["git", "pull", "--ff-only", "origin", base_branch], cwd=target_repo, dry_run=dry_run)
    r = _run(["git", "checkout", "-b", branch], cwd=target_repo, dry_run=dry_run)
    if r.returncode != 0 and not dry_run:
        errors.append(f"Branch creation failed: {r.stderr.strip()}")
        return {"branch": branch, "action": "failed", "errors": errors}

    return {"branch": branch, "action": "created", "errors": errors}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Prepare target-repo branch for Lens Dev.")
    p.add_argument("--target-repo", required=True, help="Absolute path to target repo.")
    p.add_argument("--feature-id", required=True, help="Feature identifier.")
    p.add_argument("--strategy", required=True, choices=VALID_STRATEGIES, help="Branch strategy.")
    p.add_argument("--base-branch", default="develop", help="Base branch to fork from.")
    p.add_argument("--username", default="", help="Username (required for feature-user strategy).")
    p.add_argument("--dry-run", action="store_true", help="Print git commands without executing.")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    target_repo = Path(args.target_repo)

    if not target_repo.exists():
        print(f"Error: target repo not found: {target_repo}", file=sys.stderr)
        return 1

    result = prepare_branch(
        target_repo=target_repo,
        feature_id=args.feature_id,
        strategy=args.strategy,
        base_branch=args.base_branch,
        username=args.username,
        dry_run=args.dry_run,
    )

    print(yaml.dump(result, default_flow_style=False, sort_keys=False))
    if result["errors"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
