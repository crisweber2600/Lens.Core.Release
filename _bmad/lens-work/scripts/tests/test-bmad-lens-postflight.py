#!/usr/bin/env python3
"""
test-bmad-lens-postflight.py — Tests for bmad-lens-postflight.py

Covers:
- Script is executable via sys.executable
- Exit 0 when all repos are clean (or missing)
- Exit 1 when any repo is dirty
- JSON output format
- Workspace root auto-detection
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "bmad-lens-postflight.py"


def run_postflight(
    workspace_root: str | None = None,
    target_repo: str | None = None,
    fmt: str = "text",
    extra_args: list[str] | None = None,
) -> subprocess.CompletedProcess:
    args = [sys.executable, str(SCRIPT), "--format", fmt]
    if workspace_root:
        args += ["--workspace-root", workspace_root]
    if target_repo:
        args += ["--target-repo", target_repo]
    if extra_args:
        args += extra_args
    return subprocess.run(args, capture_output=True, text=True)


class TestScriptExists(unittest.TestCase):
    def test_script_file_exists(self) -> None:
        """The bmad-lens-postflight.py script must exist."""
        self.assertTrue(SCRIPT.is_file(), f"Script not found at {SCRIPT}")

    def test_help_exits_zero(self) -> None:
        """--help exits 0."""
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)


class TestWorkspaceRootNotFound(unittest.TestCase):
    def test_exits_1_when_root_not_found(self) -> None:
        """Exits 1 when workspace root cannot be detected and no explicit root given."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [sys.executable, str(SCRIPT)],
                capture_output=True,
                text=True,
                cwd=tmpdir,
            )
        self.assertEqual(result.returncode, 1)
        self.assertIn("FAIL", result.stderr)


class TestCleanRepos(unittest.TestCase):
    """When workspace-root is supplied and all repos are non-git temp dirs, they are SKIP (not dirty)."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_missing_repos_report_skip_not_dirty_text(self) -> None:
        """Missing repos are SKIPped and not counted as dirty — exit 0."""
        result = run_postflight(
            workspace_root=str(self.root),
            fmt="text",
        )
        # Missing repos are SKIP — not dirty — so exit must be 0
        self.assertEqual(result.returncode, 0)
        self.assertIn("OK", result.stdout)

    def test_missing_repos_report_skip_not_dirty_json(self) -> None:
        """JSON output shows status=clean when all repos are missing."""
        result = run_postflight(
            workspace_root=str(self.root),
            fmt="json",
        )
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertEqual(data["status"], "clean")
        self.assertIn("repos", data)
        self.assertIsInstance(data["repos"], list)

    def test_json_repo_structure(self) -> None:
        """Each repo entry has required keys."""
        result = run_postflight(
            workspace_root=str(self.root),
            fmt="json",
        )
        data = json.loads(result.stdout)
        for repo in data["repos"]:
            self.assertIn("label", repo)
            self.assertIn("path", repo)
            self.assertIn("exists", repo)
            self.assertIn("dirty", repo)
            self.assertIn("uncommitted", repo)
            self.assertIn("unpushed", repo)

    def test_labels_are_control_governance_target(self) -> None:
        """The three repo labels are always control, governance, target."""
        result = run_postflight(workspace_root=str(self.root), fmt="json")
        data = json.loads(result.stdout)
        labels = [r["label"] for r in data["repos"]]
        self.assertEqual(labels, ["control", "governance", "target"])


class TestDirtyRepo(unittest.TestCase):
    """Simulate a dirty repo by initialising a git repo with an untracked file."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)
        self.fake_target = self.root / "my-target"
        self.fake_target.mkdir()
        # Init a git repo and leave an untracked file
        subprocess.run(["git", "init", str(self.fake_target)], capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=str(self.fake_target), capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=str(self.fake_target), capture_output=True,
        )
        (self.fake_target / "dirty.txt").write_text("dirty")

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_exits_1_when_target_is_dirty(self) -> None:
        """Exits 1 when the target repo has uncommitted changes."""
        result = run_postflight(
            workspace_root=str(self.root),
            target_repo=str(self.fake_target),
            fmt="json",
        )
        self.assertEqual(result.returncode, 1)
        data = json.loads(result.stdout)
        self.assertEqual(data["status"], "dirty")
        target_entry = next(r for r in data["repos"] if r["label"] == "target")
        self.assertTrue(target_entry["dirty"])
        self.assertGreater(len(target_entry["uncommitted"]), 0)

    def test_dirty_text_output_shows_fail(self) -> None:
        """Text output says FAIL when a repo is dirty."""
        result = run_postflight(
            workspace_root=str(self.root),
            target_repo=str(self.fake_target),
            fmt="text",
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("FAIL", result.stdout)


class TestCleanGitRepo(unittest.TestCase):
    """A freshly initialised git repo with a committed file is clean."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)
        self.fake_target = self.root / "clean-target"
        self.fake_target.mkdir()
        subprocess.run(["git", "init", str(self.fake_target)], capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=str(self.fake_target), capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=str(self.fake_target), capture_output=True,
        )
        clean_file = self.fake_target / "readme.txt"
        clean_file.write_text("hello")
        subprocess.run(
            ["git", "add", "."],
            cwd=str(self.fake_target), capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=str(self.fake_target), capture_output=True,
        )

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_exits_0_when_target_clean(self) -> None:
        """Exits 0 when target repo is fully committed (no upstream means no unpushed diff)."""
        result = run_postflight(
            workspace_root=str(self.root),
            target_repo=str(self.fake_target),
            fmt="json",
        )
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        target_entry = next(r for r in data["repos"] if r["label"] == "target")
        self.assertFalse(target_entry["dirty"])
        self.assertEqual(target_entry["uncommitted"], [])


if __name__ == "__main__":
    unittest.main()
