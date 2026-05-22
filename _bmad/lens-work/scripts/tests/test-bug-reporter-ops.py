#!/usr/bin/env python3
"""
test-bug-reporter-ops.py — End-to-end tests for bug-reporter-ops.py

Covers Story 1.1 acceptance criteria and Story 1.3 scope guard integration.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

TEST_FILE = Path(__file__).resolve()
SCRIPT = Path(__file__).parent.parent / "bug-reporter-ops.py"
FIX_SPEC_SCRIPT = TEST_FILE.parent.parent / "nextlens_fix_spec.py"
QUICKDEV_MARKER = "Bug report submitted via /lens-core-bugfix."
LEGACY_QUICKDEV_MARKER = "Bug report submitted via /lens-bug-quickdev."
FEATURE_ID = "nextlens-src-dogfoodnext"
SKILL_SOURCE_ROOT = TEST_FILE.parents[4]
CONTROL_REPO_ROOT = SKILL_SOURCE_ROOT.parents[3]


def _normalize_path_text(value: str) -> str:
    return value.replace("\\", "/")


def load_fix_spec_module():
    spec = importlib.util.spec_from_file_location("nextlens_fix_spec_for_bug_reporter_tests", FIX_SPEC_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run_create_bug(
    governance_repo: Path,
    title: str = "Test bug",
    description: str = "A test description",
    chat_log: str = "User: something broke\nAssistant: noted",
    queue: str | None = None,
    source: str | None = None,
    namespace: str | None = None,
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
    if source:
        args.extend(["--source", source])
    if namespace:
        args.extend(["--namespace", namespace])
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
    )


def run_record_quickdev_pr(
    governance_repo: Path,
    slug: str,
    pr_url: str,
    namespace: str | None = None,
) -> subprocess.CompletedProcess:
    args = [
        sys.executable,
        str(SCRIPT),
        "record-quickdev-pr",
        "--governance-repo", str(governance_repo),
        "--slug", slug,
        "--pr-url", pr_url,
    ]
    if namespace:
        args.extend(["--namespace", namespace])
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
    )


def run_close_quickdev_bug(
    governance_repo: Path,
    slug: str,
    summary: str = "Implemented the QuickDev fix",
    validation_summary: str = "Focused tests passed",
    namespace: str | None = None,
    doctor_status: str | None = None,
    doctor_evidence: str | None = None,
    doctor_rationale: str | None = None,
) -> subprocess.CompletedProcess:
    args = [
        sys.executable,
        str(SCRIPT),
        "close-quickdev-bug",
        "--governance-repo", str(governance_repo),
        "--slug", slug,
        "--summary", summary,
        "--validation-summary", validation_summary,
    ]
    if namespace:
        args.extend(["--namespace", namespace])
    if doctor_status:
        args.extend(["--doctor-status", doctor_status])
    if doctor_evidence:
        args.extend(["--doctor-evidence", doctor_evidence])
    if doctor_rationale:
        args.extend(["--doctor-rationale", doctor_rationale])
    return subprocess.run(
        args,
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

    def _write_nextlens_feature_metadata(self) -> None:
        feature_root = self.governance_repo / "features" / "nextlens" / "src" / FEATURE_ID
        feature_root.mkdir(parents=True, exist_ok=True)
        (feature_root / "feature.yaml").write_text(
            yaml.safe_dump(
                {
                    "featureId": FEATURE_ID,
                    "docs": {"path": f"docs/nextlens/src/{FEATURE_ID}"},
                    "target_repos": [
                        {"name": "lens.core.src", "local_path": "TargetProjects/lens-dev/new-codebase/lens.core.src"},
                        {"name": "NextLens", "local_path": "TargetProjects/nextlens/src/NextLens"},
                    ],
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )

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

    def test_create_bug_persists_structured_quickdev_source(self) -> None:
        """QuickDev source can be recorded structurally without relying on the chat-log body marker."""
        result = run_create_bug(
            self.governance_repo,
            chat_log="User: freeform bug transcript\nAssistant: investigating",
            queue="QuickDev",
            source="lens-core-bugfix",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        content = Path(data["path"]).read_text(encoding="utf-8")
        self.assertIn('quickdev_source: "lens-core-bugfix"', content)

    def test_nextlens_namespace_writes_namespaced_quickdev_artifact(self) -> None:
        """Namespaced NextLens intake writes to bugs/nextlens/QuickDev with namespace metadata."""
        result = run_create_bug(
            self.governance_repo,
            title="NextLens bug",
            description="Patch preview crashes in dogfood",
            chat_log="Transcript digest only\nEvidence refs: artifact://nextlens/session-17",
            queue="QuickDev",
            source="nextlens-bugfix",
            namespace="nextlens",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        path = Path(data["path"])
        self.assertTrue(path.exists())
        self.assertIn("bugs/nextlens/QuickDev", str(path).replace("\\", "/"))
        content = path.read_text(encoding="utf-8")
        self.assertIn("status: QuickDev", content)
        self.assertIn('quickdev_source: "nextlens-bugfix"', content)
        self.assertIn('namespace: "nextlens"', content)

    def test_nextlens_duplicate_lookup_is_namespaced_across_status_folders(self) -> None:
        """Duplicate detection stays within the NextLens namespace and still scans all status folders."""
        result = run_create_bug(
            self.governance_repo,
            title="Shared slug bug",
            description="Same title and description across namespaces",
            chat_log="Evidence refs: artifact://nextlens/session",
            queue="QuickDev",
            source="nextlens-bugfix",
            namespace="nextlens",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        slug = json.loads(result.stdout)["slug"]

        record = run_record_quickdev_pr(
            self.governance_repo,
            slug,
            "https://github.com/org/repo/pull/201",
            namespace="nextlens",
        )
        self.assertEqual(record.returncode, 0, record.stderr)
        close = run_close_quickdev_bug(
            self.governance_repo,
            slug,
            summary="Closed in NextLens namespace",
            validation_summary="Namespaced flow passed",
            namespace="nextlens",
            doctor_status="passed",
            doctor_evidence="artifact://doctor/namespaced-duplicate",
        )
        self.assertEqual(close.returncode, 0, close.stderr)

        duplicate = run_create_bug(
            self.governance_repo,
            title="Shared slug bug",
            description="Same title and description across namespaces",
            chat_log="Evidence refs: artifact://nextlens/session",
            queue="QuickDev",
            source="nextlens-bugfix",
            namespace="nextlens",
        )

        self.assertEqual(duplicate.returncode, 0, duplicate.stderr)
        data = json.loads(duplicate.stdout)
        self.assertEqual(data["status"], "duplicate")
        self.assertIn("bugs/nextlens/Fixed", data["path"].replace("\\", "/"))

    def test_invalid_namespace_is_rejected_before_write(self) -> None:
        """Namespace path traversal or nested path input is rejected."""
        result = run_create_bug(
            self.governance_repo,
            queue="QuickDev",
            source="nextlens-bugfix",
            namespace="../escape",
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("--namespace", result.stderr)
        self.assertFalse((self.governance_repo / "bugs" / "nextlens").exists())

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

    def test_record_quickdev_pr_accepts_legacy_bug_quickdev_marker(self) -> None:
        """Legacy /lens-bug-quickdev artifacts remain compatible with PR recording."""
        result = run_create_bug(self.governance_repo, chat_log=LEGACY_QUICKDEV_MARKER, queue="QuickDev")
        slug = json.loads(result.stdout)["slug"]

        record = run_record_quickdev_pr(self.governance_repo, slug, "https://github.com/org/repo/pull/14")

        self.assertEqual(record.returncode, 0, record.stderr)

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

    def test_record_quickdev_pr_accepts_structured_source_without_marker(self) -> None:
        """Structured quickdev provenance lets PR recording work even when chat logs are freeform."""
        result = run_create_bug(
            self.governance_repo,
            title="Structured bug",
            description="Structured source only",
            chat_log="User: freeform transcript\nAssistant: noted",
            source="lens-core-bugfix",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)

        record = run_record_quickdev_pr(self.governance_repo, data["slug"], "https://github.com/org/repo/pull/16")

        self.assertEqual(record.returncode, 0, record.stderr)
        new_path = Path(json.loads(record.stdout)["path"])
        content = new_path.read_text(encoding="utf-8")
        self.assertIn('quickdev_source: "lens-core-bugfix"', content)

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
        """record-quickdev-pr rejects a New bug that was not created by a core bugfix flow."""
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
        self.assertIn("not created by /lens-core-bugfix", record.stderr)

    def test_record_quickdev_pr_updates_only_matching_nextlens_artifact(self) -> None:
        """Namespaced PR recording updates the NextLens artifact without touching the Lens core artifact."""
        core = run_create_bug(
            self.governance_repo,
            title="Collision bug",
            description="Same slug in both namespaces",
            chat_log=QUICKDEV_MARKER,
            queue="QuickDev",
            source="lens-core-bugfix",
        )
        nextlens = run_create_bug(
            self.governance_repo,
            title="Collision bug",
            description="Same slug in both namespaces",
            chat_log="Evidence refs: artifact://nextlens/collision",
            queue="QuickDev",
            source="nextlens-bugfix",
            namespace="nextlens",
        )
        self.assertEqual(core.returncode, 0, core.stderr)
        self.assertEqual(nextlens.returncode, 0, nextlens.stderr)
        slug = json.loads(core.stdout)["slug"]
        core_path = Path(json.loads(core.stdout)["path"])

        record = run_record_quickdev_pr(
            self.governance_repo,
            slug,
            "https://github.com/org/repo/pull/301",
            namespace="nextlens",
        )

        self.assertEqual(record.returncode, 0, record.stderr)
        nextlens_path = Path(json.loads(record.stdout)["path"])
        self.assertIn("bugs/nextlens/QuickDev", str(nextlens_path).replace("\\", "/"))
        self.assertTrue(core_path.exists(), "Core QuickDev artifact should remain in place")
        self.assertNotIn("https://github.com/org/repo/pull/301", core_path.read_text(encoding="utf-8"))
        self.assertIn("https://github.com/org/repo/pull/301", nextlens_path.read_text(encoding="utf-8"))

    def test_close_quickdev_bug_moves_pr_recorded_artifact_to_fixed(self) -> None:
        """QuickDev closeout documents summary/validation and moves the artifact to Fixed."""
        result = run_create_bug(self.governance_repo, chat_log=QUICKDEV_MARKER, queue="QuickDev")
        data = json.loads(result.stdout)
        quickdev_path = Path(data["path"])
        record = run_record_quickdev_pr(self.governance_repo, data["slug"], "https://github.com/org/repo/pull/77")
        self.assertEqual(record.returncode, 0, record.stderr)

        close = run_close_quickdev_bug(
            self.governance_repo,
            data["slug"],
            summary="Added mandatory branch PR closeout workflow",
            validation_summary="Contract tests passed",
        )

        self.assertEqual(close.returncode, 0, close.stderr)
        close_data = json.loads(close.stdout)
        fixed_path = Path(close_data["path"])
        self.assertFalse(quickdev_path.exists())
        self.assertTrue(fixed_path.exists())
        self.assertIn("bugs/Fixed", str(fixed_path).replace("\\", "/"))
        content = fixed_path.read_text(encoding="utf-8")
        self.assertIn("status: Fixed", content)
        self.assertIn("closed_at:", content)
        self.assertIn("closeout_summary:", content)
        self.assertIn("validation_summary:", content)
        self.assertIn("## QuickDev Closeout", content)
        self.assertIn("Summary: Added mandatory branch PR closeout workflow", content)
        self.assertIn("Validation: Contract tests passed", content)

    def test_close_quickdev_bug_moves_only_matching_nextlens_artifact(self) -> None:
        """Namespaced closeout moves only the NextLens artifact into bugs/nextlens/Fixed."""
        core = run_create_bug(
            self.governance_repo,
            title="Closeout collision bug",
            description="Same slug in both namespaces",
            chat_log=QUICKDEV_MARKER,
            queue="QuickDev",
            source="lens-core-bugfix",
        )
        nextlens = run_create_bug(
            self.governance_repo,
            title="Closeout collision bug",
            description="Same slug in both namespaces",
            chat_log="Evidence refs: artifact://nextlens/closeout",
            queue="QuickDev",
            source="nextlens-bugfix",
            namespace="nextlens",
        )
        self.assertEqual(core.returncode, 0, core.stderr)
        self.assertEqual(nextlens.returncode, 0, nextlens.stderr)
        slug = json.loads(nextlens.stdout)["slug"]
        core_path = Path(json.loads(core.stdout)["path"])

        record = run_record_quickdev_pr(
            self.governance_repo,
            slug,
            "https://github.com/org/repo/pull/302",
            namespace="nextlens",
        )
        self.assertEqual(record.returncode, 0, record.stderr)

        close = run_close_quickdev_bug(
            self.governance_repo,
            slug,
            summary="Closed NextLens bug only",
            validation_summary="Namespaced regression tests passed",
            namespace="nextlens",
            doctor_status="passed",
            doctor_evidence="artifact://doctor/nextlens-closeout-collision",
        )

        self.assertEqual(close.returncode, 0, close.stderr)
        fixed_path = Path(json.loads(close.stdout)["path"])
        self.assertIn("bugs/nextlens/Fixed", str(fixed_path).replace("\\", "/"))
        self.assertTrue(core_path.exists(), "Core QuickDev artifact should not move during namespaced closeout")
        self.assertIn("bugs/QuickDev", str(core_path).replace("\\", "/"))
        content = fixed_path.read_text(encoding="utf-8")
        self.assertIn('namespace: "nextlens"', content)
        self.assertIn('doctor_status: "passed"', content)
        self.assertIn('doctor_evidence: "artifact://doctor/nextlens-closeout-collision"', content)
        self.assertIn("NextLens Doctor: passed", content)
        self.assertIn("Doctor evidence: artifact://doctor/nextlens-closeout-collision", content)

    def test_nextlens_closeout_accepts_doctor_not_applicable_rationale(self) -> None:
        """NextLens closeout can proceed when Doctor is not applicable and the rationale is recorded."""
        result = run_create_bug(
            self.governance_repo,
            title="Doctor NA bug",
            description="Validation route does not apply",
            chat_log="Evidence refs: artifact://nextlens/doctor-na",
            queue="QuickDev",
            source="nextlens-bugfix",
            namespace="nextlens",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        record = run_record_quickdev_pr(self.governance_repo, data["slug"], "https://github.com/org/repo/pull/410", namespace="nextlens")
        self.assertEqual(record.returncode, 0, record.stderr)

        close = run_close_quickdev_bug(
            self.governance_repo,
            data["slug"],
            namespace="nextlens",
            doctor_status="not-applicable",
            doctor_rationale="Doctor does not run against this design-only bugfix surface.",
        )

        self.assertEqual(close.returncode, 0, close.stderr)
        fixed_path = Path(json.loads(close.stdout)["path"])
        content = fixed_path.read_text(encoding="utf-8")
        self.assertIn("bugs/nextlens/Fixed", str(fixed_path).replace("\\", "/"))
        self.assertIn('doctor_status: "not-applicable"', content)
        self.assertIn(
            'doctor_rationale: "Doctor does not run against this design-only bugfix surface."',
            content,
        )
        self.assertIn("Doctor rationale: Doctor does not run against this design-only bugfix surface.", content)

    def test_nextlens_closeout_requires_doctor_validation_evidence(self) -> None:
        """NextLens closeout blocks when neither Doctor evidence nor a valid rationale is recorded."""
        result = run_create_bug(
            self.governance_repo,
            title="Doctor required bug",
            description="Missing doctor evidence should block",
            chat_log="Evidence refs: artifact://nextlens/doctor-required",
            queue="QuickDev",
            source="nextlens-bugfix",
            namespace="nextlens",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        record = run_record_quickdev_pr(self.governance_repo, data["slug"], "https://github.com/org/repo/pull/411", namespace="nextlens")
        self.assertEqual(record.returncode, 0, record.stderr)

        missing_status = run_close_quickdev_bug(
            self.governance_repo,
            data["slug"],
            namespace="nextlens",
        )
        self.assertEqual(missing_status.returncode, 1)
        self.assertIn("NextLens closeout requires --doctor-status", missing_status.stderr)

        missing_evidence = run_close_quickdev_bug(
            self.governance_repo,
            data["slug"],
            namespace="nextlens",
            doctor_status="passed",
        )
        self.assertEqual(missing_evidence.returncode, 1)
        self.assertIn("requires --doctor-evidence", missing_evidence.stderr)

    def test_nextlens_closeout_requires_recorded_pr_url(self) -> None:
        """NextLens closeout still blocks until a PR URL has been recorded."""
        result = run_create_bug(
            self.governance_repo,
            title="NextLens PR required bug",
            description="Missing PR evidence should block",
            chat_log="Evidence refs: artifact://nextlens/pr-required",
            queue="QuickDev",
            source="nextlens-bugfix",
            namespace="nextlens",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)

        close = run_close_quickdev_bug(
            self.governance_repo,
            data["slug"],
            namespace="nextlens",
            doctor_status="passed",
            doctor_evidence="artifact://doctor/pr-required",
        )

        self.assertEqual(close.returncode, 1)
        self.assertIn("recorded PR URL", close.stderr)

    def test_nextlens_closeout_records_approved_route_for_high_salmon_signals(self) -> None:
        """High-severity Salmon-linked NextLens closeout records approved-route evidence."""
        result = run_create_bug(
            self.governance_repo,
            title="High Salmon bug",
            description="Requires approved route evidence",
            chat_log=(
                "Evidence refs: artifact://nextlens/high-salmon\n"
                "Severity: High\n"
                "Salmon Signal ID: salmon.20260515T210000Z.high"
            ),
            queue="QuickDev",
            source="nextlens-bugfix",
            namespace="nextlens",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        record = run_record_quickdev_pr(self.governance_repo, data["slug"], "https://github.com/org/repo/pull/412", namespace="nextlens")
        self.assertEqual(record.returncode, 0, record.stderr)

        close = run_close_quickdev_bug(
            self.governance_repo,
            data["slug"],
            namespace="nextlens",
            doctor_status="passed",
            doctor_evidence="artifact://doctor/high-salmon",
        )

        self.assertEqual(close.returncode, 0, close.stderr)
        fixed_path = Path(json.loads(close.stdout)["path"])
        content = fixed_path.read_text(encoding="utf-8")
        self.assertIn('approved_route_evidence: "Approved NextLens closeout route used via record-quickdev-pr and close-quickdev-bug. PR URL: https://github.com/org/repo/pull/412. Doctor status: passed. Doctor evidence: artifact://doctor/high-salmon."', content)
        self.assertIn("Approved route evidence: Approved NextLens closeout route used via record-quickdev-pr and close-quickdev-bug.", content)

    def test_nextlens_end_to_end_flow_stays_deterministic_from_intake_to_closeout(self) -> None:
        """Observed/expected chat intake produces deterministic namespaced artifact, fix spec, PR evidence, and closeout state."""
        self._write_nextlens_feature_metadata()
        fix_spec = load_fix_spec_module()

        intake = {
            "what_happened": "Selecting a patch target in the dogfood chat closes the preview pane and restarts the session.",
            "what_should_have_happened": "The patch preview should stay open and show the selected target without restarting.",
            "chat_history": (
                "User: I selected the dogfood patch target and the preview disappeared.\n"
                "Assistant: I saw the restart after target selection.\n"
                "User: Expected the preview to stay open so I could confirm the patch."
            ),
            "severity": "high",
            "salmon_signal_id": "salmon.20260515T220000Z.high_patch_preview",
            "evidence_refs": ["artifact://nextlens/session-19", "artifact://nextlens/doctor/preview"],
            "suspected_target_surface": r"TargetProjects\nextlens\src\NextLens\Runtime\PatchPreview",
            "validation_request": "Run NextLens Doctor patch-preview regression and capture the output reference.",
        }

        spec = fix_spec.generate_nextlens_fix_spec(
            FEATURE_ID,
            intake,
            bug_state={
                "status": "QuickDev",
                "namespace": "nextlens",
                "governance_repo_root": str(self.governance_repo),
            },
            start=str(CONTROL_REPO_ROOT),
            governance_repo=str(self.governance_repo),
        )

        self.assertEqual(spec["status"], "ready")
        self.assertEqual(spec["bugfix_feature_id"], f"nextlens-bugfix-{spec['bug_slug']}")
        self.assertEqual(spec["bugfix_feature_slug"], spec["bugfix_feature_id"])
        self.assertEqual(spec["bugfix_working_branch"], f"feature/{spec['bugfix_feature_id']}")
        expected_quickdev_path = (self.governance_repo / "bugs" / "nextlens" / "QuickDev" / f"{spec['bug_slug']}.md").resolve()
        self.assertEqual(Path(spec["bug_artifact_path"]).resolve(), expected_quickdev_path)
        self.assertEqual(
            [_normalize_path_text(path) for path in spec["suspected_target_surfaces"]],
            [(CONTROL_REPO_ROOT / "TargetProjects" / "nextlens" / "src" / "NextLens" / "Runtime" / "PatchPreview").resolve().as_posix()],
        )
        self.assertEqual(
            spec["validation_expectations"][0],
            "Run NextLens Doctor patch-preview regression and capture the output reference.",
        )
        self.assertEqual(
            spec["salmon_linkage"]["signal_id"],
            "salmon.20260515T220000Z.high_patch_preview",
        )

        create = run_create_bug(
            self.governance_repo,
            title=spec["bug_reporter_fields"]["title"],
            description=spec["bug_reporter_fields"]["description"],
            chat_log=spec["bug_reporter_fields"]["chat_log"],
            queue=spec["bug_reporter_fields"]["queue"],
            source=spec["bug_reporter_fields"]["source"],
            namespace=spec["bug_reporter_fields"]["namespace"],
        )
        self.assertEqual(create.returncode, 0, create.stderr)
        created = json.loads(create.stdout)
        self.assertEqual(created["status"], "created")
        self.assertEqual(created["slug"], spec["bug_slug"])
        self.assertEqual(Path(created["path"]).resolve(), expected_quickdev_path)

        pr_url = "https://github.com/org/NextLens/pull/901"
        record = run_record_quickdev_pr(self.governance_repo, spec["bug_slug"], pr_url, namespace="nextlens")
        self.assertEqual(record.returncode, 0, record.stderr)
        recorded = json.loads(record.stdout)
        self.assertEqual(recorded["path"], spec["bug_artifact_path"])
        self.assertEqual(recorded["pr_url"], pr_url)

        close = run_close_quickdev_bug(
            self.governance_repo,
            spec["bug_slug"],
            summary="Fixed the dogfood patch preview restart after target selection.",
            validation_summary="NextLens Doctor patch-preview regression passed; transcript-derived repro validated.",
            namespace="nextlens",
            doctor_status="passed",
            doctor_evidence="artifact://doctor/patch-preview-pass",
        )
        self.assertEqual(close.returncode, 0, close.stderr)
        closed = json.loads(close.stdout)
        fixed_path = Path(closed["path"]).resolve()
        self.assertEqual(closed["status"], "closed")
        self.assertEqual(fixed_path, (self.governance_repo / "bugs" / "nextlens" / "Fixed" / f"{spec['bug_slug']}.md").resolve())
        content = fixed_path.read_text(encoding="utf-8")
        self.assertIn('status: Fixed', content)
        self.assertIn(f'pr_url: "{pr_url}"', content)
        self.assertIn('doctor_status: "passed"', content)
        self.assertIn('doctor_evidence: "artifact://doctor/patch-preview-pass"', content)
        self.assertIn("Summary: Fixed the dogfood patch preview restart after target selection.", content)
        self.assertIn("Validation: NextLens Doctor patch-preview regression passed; transcript-derived repro validated.", content)
        self.assertIn("Approved route evidence: Approved NextLens closeout route used via record-quickdev-pr and close-quickdev-bug.", content)

    def test_core_quickdev_regression_remains_root_scoped_with_nextlens_namespace_present(self) -> None:
        """Existing bugs/QuickDev behavior stays unchanged even when a NextLens namespaced artifact exists."""
        nextlens = run_create_bug(
            self.governance_repo,
            title="Shared root regression bug",
            description="Same slug in both namespaces",
            chat_log="Evidence refs: artifact://nextlens/root-regression",
            queue="QuickDev",
            source="nextlens-bugfix",
            namespace="nextlens",
        )
        core = run_create_bug(
            self.governance_repo,
            title="Shared root regression bug",
            description="Same slug in both namespaces",
            chat_log=QUICKDEV_MARKER,
            queue="QuickDev",
            source="lens-core-bugfix",
        )
        self.assertEqual(nextlens.returncode, 0, nextlens.stderr)
        self.assertEqual(core.returncode, 0, core.stderr)
        nextlens_path = Path(json.loads(nextlens.stdout)["path"])
        slug = json.loads(core.stdout)["slug"]

        record = run_record_quickdev_pr(self.governance_repo, slug, "https://github.com/org/repo/pull/509")
        self.assertEqual(record.returncode, 0, record.stderr)
        close = run_close_quickdev_bug(
            self.governance_repo,
            slug,
            summary="Lens core QuickDev regression still closes through the root queue.",
            validation_summary="Legacy lens-core-bugfix closeout regression passed.",
        )
        self.assertEqual(close.returncode, 0, close.stderr)

        fixed_path = Path(json.loads(close.stdout)["path"])
        self.assertIn("bugs/Fixed", str(fixed_path).replace("\\", "/"))
        self.assertNotIn("bugs/nextlens/Fixed", str(fixed_path).replace("\\", "/"))
        content = fixed_path.read_text(encoding="utf-8")
        self.assertNotIn('namespace: "nextlens"', content)
        self.assertNotIn("doctor_status:", content)
        self.assertTrue(nextlens_path.exists(), "NextLens namespaced artifact should not be moved by the core regression flow")

    def test_close_quickdev_bug_accepts_structured_source_without_marker(self) -> None:
        """Structured quickdev provenance lets closeout succeed even if the chat-log text changes."""
        result = run_create_bug(
            self.governance_repo,
            chat_log="User: freeform transcript\nAssistant: noted",
            queue="QuickDev",
            source="lens-core-bugfix",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        record = run_record_quickdev_pr(self.governance_repo, data["slug"], "https://github.com/org/repo/pull/117")
        self.assertEqual(record.returncode, 0, record.stderr)

        close = run_close_quickdev_bug(self.governance_repo, data["slug"])

        self.assertEqual(close.returncode, 0, close.stderr)
        fixed_path = Path(json.loads(close.stdout)["path"])
        self.assertTrue(fixed_path.exists())
        self.assertIn('quickdev_source: "lens-core-bugfix"', fixed_path.read_text(encoding="utf-8"))

    def test_close_quickdev_bug_requires_recorded_pr(self) -> None:
        """QuickDev closeout blocks until a PR URL has been recorded."""
        result = run_create_bug(self.governance_repo, chat_log=QUICKDEV_MARKER, queue="QuickDev")
        data = json.loads(result.stdout)

        close = run_close_quickdev_bug(self.governance_repo, data["slug"])

        self.assertEqual(close.returncode, 1)
        self.assertIn("recorded PR URL", close.stderr)

    def test_record_quickdev_pr_updates_already_fixed_artifact(self) -> None:
        """PR recording remains idempotent after QuickDev closeout."""
        result = run_create_bug(self.governance_repo, chat_log=QUICKDEV_MARKER, queue="QuickDev")
        data = json.loads(result.stdout)
        run_record_quickdev_pr(self.governance_repo, data["slug"], "https://github.com/org/repo/pull/88")
        close = run_close_quickdev_bug(self.governance_repo, data["slug"])
        self.assertEqual(close.returncode, 0, close.stderr)

        record = run_record_quickdev_pr(self.governance_repo, data["slug"], "https://github.com/org/repo/pull/89")

        self.assertEqual(record.returncode, 0, record.stderr)
        record_data = json.loads(record.stdout)
        fixed_path = Path(record_data["path"])
        self.assertIn("bugs/Fixed", str(fixed_path).replace("\\", "/"))
        content = fixed_path.read_text(encoding="utf-8")
        self.assertIn('status: Fixed', content)
        self.assertIn('pr_url: "https://github.com/org/repo/pull/89"', content)


if __name__ == "__main__":
    unittest.main()
