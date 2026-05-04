#!/usr/bin/env python3
"""
test-bug-reporter-ops.py — End-to-end tests for bug-reporter-ops.py

Covers Story 1.1 acceptance criteria and Story 1.3 scope guard integration.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "bug-reporter-ops.py"
QUICKDEV_MARKER = "Bug report submitted via /lens-bug-quickdev."


def run_create_bug(
    governance_repo: Path,
    title: str = "Test bug",
    description: str = "A test description",
    chat_log: str = "User: something broke\nAssistant: noted",
    queue: str | None = None,
) -> subprocess.CompletedProcess:
    args = [
        sys.executable,
        str(SCRIPT),
        "create-bug",
        "--title", title,
        "--description", description,
        "--chat-log", chat_log,
        "--governance-repo", str(governance_repo),
    ]
    if queue:
        args.extend(["--queue", queue])
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
    )


def run_record_quickdev_pr(governance_repo: Path, slug: str, pr_url: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "record-quickdev-pr",
            "--governance-repo", str(governance_repo),
            "--slug", slug,
            "--pr-url", pr_url,
        ],
        capture_output=True,
        text=True,
    )


def run_migrate_quickdev_bugs(governance_repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "migrate-quickdev-bugs",
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

    def test_quickdev_queue_creates_artifact_in_quickdev_folder(self) -> None:
        """QuickDev intake writes governance_repo/bugs/QuickDev/{slug}.md with status=QuickDev."""
        result = run_create_bug(self.governance_repo, chat_log=QUICKDEV_MARKER, queue="QuickDev")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        path = Path(data["path"])
        self.assertTrue(path.exists(), f"Expected artifact at {path}")
        self.assertIn("bugs/QuickDev", str(path).replace("\\", "/"))
        content = path.read_text(encoding="utf-8")
        self.assertIn("status: QuickDev", content)

    def test_quickdev_queue_duplicate_rerun_returns_existing_path(self) -> None:
        """QuickDev intake remains idempotent inside the QuickDev folder."""
        run_create_bug(self.governance_repo, chat_log=QUICKDEV_MARKER, queue="QuickDev")
        result = run_create_bug(self.governance_repo, chat_log=QUICKDEV_MARKER, queue="QuickDev")

        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["status"], "duplicate")
        self.assertIn("bugs/QuickDev", data["path"].replace("\\", "/"))
        files = list((self.governance_repo / "bugs" / "QuickDev").glob("*.md"))
        self.assertEqual(len(files), 1)

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

    def test_record_quickdev_pr_updates_artifact(self) -> None:
        """Recording a PR adds frontmatter and a body section to the QuickDev artifact."""
        result = run_create_bug(self.governance_repo, chat_log=QUICKDEV_MARKER, queue="QuickDev")
        slug = json.loads(result.stdout)["slug"]

        record = run_record_quickdev_pr(self.governance_repo, slug, "https://github.com/org/repo/pull/12")

        self.assertEqual(record.returncode, 0, record.stderr)
        data = json.loads(record.stdout)
        path = Path(data["path"])
        content = path.read_text(encoding="utf-8")
        self.assertIn('pr_url: "https://github.com/org/repo/pull/12"', content)
        self.assertIn("pr_recorded_at:", content)
        self.assertIn("## QuickDev PR", content)
        self.assertIn("PR URL: https://github.com/org/repo/pull/12", content)

    def test_record_quickdev_pr_moves_legacy_new_artifact(self) -> None:
        """Recording a PR moves a legacy quickdev artifact from New to QuickDev."""
        result = run_create_bug(self.governance_repo, chat_log=QUICKDEV_MARKER)
        data = json.loads(result.stdout)
        old_path = Path(data["path"])

        record = run_record_quickdev_pr(self.governance_repo, data["slug"], "https://github.com/org/repo/pull/13")

        self.assertEqual(record.returncode, 0, record.stderr)
        self.assertFalse(old_path.exists())
        new_path = Path(json.loads(record.stdout)["path"])
        self.assertTrue(new_path.exists())
        self.assertIn("bugs/QuickDev", str(new_path).replace("\\", "/"))
        self.assertIn("status: QuickDev", new_path.read_text(encoding="utf-8"))

    def test_migrate_quickdev_bugs_moves_only_quickdev_marked_files(self) -> None:
        """Migration moves existing quickdev intake files and leaves normal New bugs alone."""
        quick = run_create_bug(
            self.governance_repo,
            title="Quick bug",
            description="Quick description",
            chat_log=QUICKDEV_MARKER,
        )
        normal = run_create_bug(
            self.governance_repo,
            title="Normal bug",
            description="Normal description",
            chat_log="Bug report submitted via /lens-bug-reporter.",
        )
        quick_slug = json.loads(quick.stdout)["slug"]
        normal_slug = json.loads(normal.stdout)["slug"]

        migrated = run_migrate_quickdev_bugs(self.governance_repo)

        self.assertEqual(migrated.returncode, 0, migrated.stderr)
        data = json.loads(migrated.stdout)
        self.assertEqual(data["moved"], [quick_slug])
        self.assertTrue((self.governance_repo / "bugs" / "QuickDev" / f"{quick_slug}.md").exists())
        self.assertTrue((self.governance_repo / "bugs" / "New" / f"{normal_slug}.md").exists())
        self.assertFalse((self.governance_repo / "bugs" / "New" / f"{quick_slug}.md").exists())

    def test_help_exits_0(self) -> None:
        """Script accepts --help cleanly (§7.3 scan-scripts)."""
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)

    def test_emoji_only_title_creates_valid_slug(self) -> None:
        """Title with no ASCII letters/digits (e.g. emoji) uses 'bug-{hash}' fallback slug."""
        result = run_create_bug(self.governance_repo, title="🐛🔥", description="pure emoji title")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        slug = data["slug"]
        # Must start with 'bug-' prefix and end with 8-char hex hash
        self.assertRegex(slug, r'^[a-z0-9][a-z0-9-]*-[0-9a-f]{8}$', f"Invalid slug: {slug}")
        self.assertTrue(slug.startswith("bug-"), f"Expected 'bug-' prefix, got: {slug}")

    def test_record_quickdev_pr_emoji_slug_accepted(self) -> None:
        """record-quickdev-pr succeeds for a bug whose slug came from an emoji-only title."""
        result = run_create_bug(
            self.governance_repo,
            title="🐛🔥",
            description="pure emoji title",
            chat_log=QUICKDEV_MARKER,
            queue="QuickDev",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        slug = json.loads(result.stdout)["slug"]
        record = run_record_quickdev_pr(self.governance_repo, slug, "https://github.com/org/repo/pull/99")
        self.assertEqual(record.returncode, 0, record.stderr)

    def test_record_quickdev_pr_rejects_non_quickdev_new_bug(self) -> None:
        """record-quickdev-pr rejects a New bug that was not created by /lens-bug-quickdev."""
        result = run_create_bug(
            self.governance_repo,
            title="Normal bug",
            description="Created via normal reporter",
            chat_log="Bug report submitted via /lens-bug-reporter.",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        slug = json.loads(result.stdout)["slug"]

        record = run_record_quickdev_pr(self.governance_repo, slug, "https://github.com/org/repo/pull/55")
        self.assertEqual(record.returncode, 1)
        self.assertIn("not created by /lens-bug-quickdev", record.stderr)


if __name__ == "__main__":
    unittest.main()
