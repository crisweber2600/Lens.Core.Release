#!/usr/bin/env python3
"""
test-bugbash-scope-guard.py — Unit tests for bugbash_scope_guard.py

Covers regression category § 7.2 from tech-plan:
  - Write to bugs/New/ within governance_repo → PASS
  - Write to path outside governance_repo → Blocked; scope violation error
  - Write to governance_repo/features/lens-dev/old-codebase/ → Blocked
  - Write to governance_repo/features/lens-dev/new-codebase/ → PASS
  - governance_repo path does not exist → exit 1 with config error (A7)
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

# Allow running from anywhere
sys.path.insert(0, str(Path(__file__).parent.parent))

from bugbash_scope_guard import (
    ScopeViolationError,
    assert_governance_repo_exists,
    assert_path_in_scope,
)


class TestAssertPathInScope(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Path("/governance")

    def _path(self, *parts: str) -> Path:
        return Path(self.repo, *parts)

    def test_bugs_new_is_allowed(self) -> None:
        """Write to bugs/New/ within governance_repo → PASS."""
        assert_path_in_scope(self._path("bugs", "New", "my-bug.md"), self.repo)

    def test_bugs_inprogress_is_allowed(self) -> None:
        assert_path_in_scope(self._path("bugs", "Inprogress", "my-bug.md"), self.repo)

    def test_bugs_fixed_is_allowed(self) -> None:
        assert_path_in_scope(self._path("bugs", "Fixed", "my-bug.md"), self.repo)

    def test_features_new_codebase_is_allowed(self) -> None:
        """Write to governance_repo/features/lens-dev/new-codebase/ → PASS."""
        assert_path_in_scope(
            self._path("features", "lens-dev", "new-codebase", "some-feature", "feature.yaml"),
            self.repo,
        )

    def test_outside_governance_repo_is_blocked(self) -> None:
        """Write to path outside governance_repo → Blocked."""
        with self.assertRaises(ScopeViolationError):
            assert_path_in_scope(Path("/other/path/file.md"), self.repo)

    def test_features_old_codebase_is_blocked(self) -> None:
        """Write to governance_repo/features/lens-dev/old-codebase/ → Blocked."""
        with self.assertRaises(ScopeViolationError):
            assert_path_in_scope(
                self._path("features", "lens-dev", "old-codebase", "some-feature", "feature.yaml"),
                self.repo,
            )

    def test_governance_root_itself_is_blocked(self) -> None:
        """The repo root is not in scope."""
        with self.assertRaises(ScopeViolationError):
            assert_path_in_scope(self.repo / "feature-index.yaml", self.repo)

    def test_error_message_contains_scope_violation(self) -> None:
        """Error message explicitly labels a scope violation."""
        with self.assertRaises(ScopeViolationError) as ctx:
            assert_path_in_scope(Path("/other/bad.md"), self.repo)
        self.assertIn("Scope violation", str(ctx.exception))
        self.assertIn("No file was written", str(ctx.exception))


class TestAssertGovernanceRepoExists(unittest.TestCase):
    def test_missing_repo_exits_1(self) -> None:
        """governance_repo does not exist → exit 1 with config error (A7)."""
        missing = Path("/nonexistent/repo")
        with self.assertRaises(SystemExit) as ctx:
            assert_governance_repo_exists(missing)
        self.assertEqual(ctx.exception.code, 1)

    def test_existing_repo_does_not_exit(self, tmp_path: Path = None) -> None:
        """governance_repo exists → no exit."""
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            assert_governance_repo_exists(Path(d))  # should not raise


if __name__ == "__main__":
    unittest.main()
