#!/usr/bin/env python3
"""
test-bug-reporter-ops.py — End-to-end tests for bug-reporter-ops.py

Covers Story 1.1 acceptance criteria and Story 1.3 scope guard integration.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "bug-reporter-ops.py"


def run_create_bug(
    governance_repo: Path,
    title: str = "Test bug",
    description: str = "A test description",
    chat_log: str = "User: something broke\nAssistant: noted",
) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "create-bug",
            "--title", title,
            "--description", description,
            "--chat-log", chat_log,
            "--governance-repo", str(governance_repo),
        ],
        capture_output=True,
        text=True,
    )


class TestCreateBugEndToEnd(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.governance_repo = Path(self._tmpdir.name)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_creates_artifact_at_correct_path(self) -> None:
        """✅ creates one artifact at governance_repo/bugs/New/{slug}.md"""
        result = run_create_bug(self.governance_repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["status"], "created")
        path = Path(data["path"])
        self.assertTrue(path.exists(), f"Expected artifact at {path}")
        self.assertTrue(str(path).endswith(".md"))
        self.assertIn("bugs/New", str(path).replace("\\", "/"))

    def test_artifact_has_valid_frontmatter(self) -> None:
        """Artifact contains valid frontmatter: title, description, status=New, featureId=\"\""""
        result = run_create_bug(self.governance_repo)
        data = json.loads(result.stdout)
        content = Path(data["path"]).read_text(encoding="utf-8")
        self.assertIn("status: New", content)
        self.assertIn('featureId: ""', content)
        self.assertIn("Test bug", content)

    def test_idempotent_rerun_returns_duplicate(self) -> None:
        """Idempotent: re-run with identical inputs returns 'duplicate'; no second artifact."""
        run_create_bug(self.governance_repo)
        result2 = run_create_bug(self.governance_repo)
        self.assertEqual(result2.returncode, 0, result2.stderr)
        data = json.loads(result2.stdout)
        self.assertEqual(data["status"], "duplicate")
        # Only one file in New/
        new_dir = self.governance_repo / "bugs" / "New"
        files = list(new_dir.glob("*.md"))
        self.assertEqual(len(files), 1)

    def test_missing_title_exits_1(self) -> None:
        """Missing title → exit 1; no file written."""
        result = run_create_bug(self.governance_repo, title="")
        self.assertEqual(result.returncode, 1)
        new_dir = self.governance_repo / "bugs" / "New"
        self.assertFalse(new_dir.exists() and any(new_dir.glob("*.md")))

    def test_missing_description_exits_1(self) -> None:
        """Missing description → exit 1; no file written."""
        result = run_create_bug(self.governance_repo, description="")
        self.assertEqual(result.returncode, 1)

    def test_missing_governance_repo_exits_1(self) -> None:
        """governance_repo does not exist → exit 1 with config error (A7)."""
        # Use a path that is provably absent: a deleted temp dir
        with tempfile.TemporaryDirectory() as d:
            missing = Path(d) / "definitely_missing_subdir"
        # missing is now outside the context manager; the parent was cleaned up
        result = run_create_bug(missing)
        self.assertEqual(result.returncode, 1)
        self.assertIn("governance_repo", result.stderr)

    def test_parent_directories_created_if_missing(self) -> None:
        """Missing parent directories (bugs/New/) are created (A4)."""
        # governance_repo exists but bugs/ subfolders do not
        result = run_create_bug(self.governance_repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.governance_repo / "bugs" / "New").exists())

    def test_chat_log_in_body(self) -> None:
        """Chat log content follows frontmatter as markdown body."""
        chat = "User: the thing broke\nAssistant: acknowledged"
        result = run_create_bug(self.governance_repo, chat_log=chat)
        data = json.loads(result.stdout)
        content = Path(data["path"]).read_text(encoding="utf-8")
        self.assertIn(chat, content)

    def test_help_exits_0(self) -> None:
        """Script accepts --help cleanly (§7.3 scan-scripts)."""
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
