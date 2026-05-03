#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
bugbash_scope_guard.py — Shared scope-guard utility for all bugbash scripts.

Hard-blocks any path that is not inside one of the two authorized prefixes:
  - governance_repo/bugs/
  - governance_repo/features/lens-dev/new-codebase/

Import and call assert_path_in_scope() before every file operation.
"""

from __future__ import annotations

import sys
from pathlib import Path


class ScopeViolationError(Exception):
    """Raised when a path is outside the authorized bugbash scope."""


def _authorized_prefixes(governance_repo: Path) -> tuple[Path, Path]:
    """Return the two hard-coded authorized path prefixes."""
    return (
        governance_repo / "bugs",
        governance_repo / "features" / "lens-dev" / "new-codebase",
    )


def assert_governance_repo_exists(governance_repo: Path) -> None:
    """Startup validation: exit 1 with a clear config error if the repo is missing.

    All three bugbash scripts must call this before any file operations.
    """
    if not governance_repo.exists():
        print(
            f"ERROR: governance_repo does not exist: {governance_repo}\n"
            "Check your --governance-repo argument and ensure the path is correct.",
            file=sys.stderr,
        )
        sys.exit(1)


def assert_path_in_scope(path: Path, governance_repo: Path) -> None:
    """Raise ScopeViolationError if *path* is not inside an authorized prefix.

    Args:
        path: Resolved absolute path to validate.
        governance_repo: Resolved absolute path to the governance repository root.

    Raises:
        ScopeViolationError: If the path is outside the authorized scope.
    """
    path = Path(path).resolve()
    governance_repo = Path(governance_repo).resolve()

    bugs_prefix, features_prefix = _authorized_prefixes(governance_repo)

    try:
        path.relative_to(bugs_prefix)
        return  # within bugs/ — allowed
    except ValueError:
        pass

    try:
        path.relative_to(features_prefix)
        return  # within features/lens-dev/new-codebase/ — allowed
    except ValueError:
        pass

    raise ScopeViolationError(
        f"Scope violation: path '{path}' is outside authorized bugbash scope.\n"
        f"  Allowed prefixes:\n"
        f"    {bugs_prefix}\n"
        f"    {features_prefix}\n"
        "No file was written or modified."
    )
