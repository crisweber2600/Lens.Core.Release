"""
Tests for bug-fixer-ops.py — Story 2.1-2.4 regression tests.
Covers: discover-new, move-to-inprogress, move-to-fixed, resolve-bugs
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).parent.parent / "bug-fixer-ops.py"
)


def test_pyyaml_is_importable():
    """FINDING-PD04: pyyaml must be available; script raises ImportError otherwise."""
    import importlib
    assert importlib.util.find_spec("yaml") is not None, (
        "pyyaml is not installed — run via `uv run --script bug-fixer-ops.py` "
        "or install pyyaml>=6.0 in the active environment"
    )


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
    )


def _make_bug_file(
    parent_dir: Path,
    slug: str,
    status: str = "New",
    feature_id: str = "",
) -> Path:
    """Create a minimal bug markdown file and return the path."""
    parent_dir.mkdir(parents=True, exist_ok=True)
    content = textwrap.dedent(f"""\
        ---
        title: "Bug {slug}"
        description: "Description of {slug}"
        status: "{status}"
        slug: "{slug}"
        featureId: "{feature_id}"
        created_at: "2025-01-01T00:00:00Z"
        updated_at: "2025-01-01T00:00:00Z"
        ---

        ## Chat Log

        Chat log here.
    """)
    path = parent_dir / f"{slug}.md"
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# discover-new
# ---------------------------------------------------------------------------


class TestDiscoverNew:
    def test_discover_new_returns_empty_when_no_bugs_dir(self, tmp_path):
        governance_repo = tmp_path / "gov"
        governance_repo.mkdir()
        result = _run(["discover-new", "--governance-repo", str(governance_repo)])
        assert result.returncode == 0
        data = json.loads(result.stdout.strip())
        assert data["count"] == 0
        assert data["bugs"] == []

    def test_discover_new_returns_bugs_in_new_folder(self, tmp_path):
        governance_repo = tmp_path / "gov"
        bugs_new = governance_repo / "bugs" / "New"
        _make_bug_file(bugs_new, "login-crash-abc12345", status="New")
        _make_bug_file(bugs_new, "logout-hang-def67890", status="New")
        result = _run(["discover-new", "--governance-repo", str(governance_repo)])
        assert result.returncode == 0
        data = json.loads(result.stdout.strip())
        assert data["count"] == 2
        slugs = [b["slug"] for b in data["bugs"]]
        assert "login-crash-abc12345" in slugs
        assert "logout-hang-def67890" in slugs

    def test_discover_new_exits_1_when_governance_repo_missing(self):
        with tempfile.TemporaryDirectory() as td:
            missing = Path(td) / "does-not-exist"
        result = _run(["discover-new", "--governance-repo", str(missing)])
        assert result.returncode == 1

    def test_help_exits_0(self):
        result = _run(["--help"])
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# derive-feature-id
# ---------------------------------------------------------------------------


class TestDeriveFeatureId:
    def test_single_slug_is_deterministic(self):
        result = _run([
            "derive-feature-id",
            "--slugs", "reporter-fixed-bug",
        ])
        assert result.returncode == 0
        data = json.loads(result.stdout.strip())
        assert data["stub"] == "reporter-fixed-bug"
        assert data["feature_id"] == (
            "lens-dev-new-codebase-bugfix-reporter-fixed-bug"
        )

    def test_long_slug_truncated_to_safe_id_limit(self):
        # slug with 40 chars gets capped to 35 to keep total feature_id <= 64 chars
        result = _run([
            "derive-feature-id",
            "--slugs", "preflight-failed-and-reporter-fixed-bug",
        ])
        assert result.returncode == 0
        data = json.loads(result.stdout.strip())
        # stub is trimmed to 35 chars (64 - len("lens-dev-new-codebase-bugfix-"))
        assert data["stub"] == "preflight-failed-and-reporter-fixed"
        assert data["feature_id"] == (
            "lens-dev-new-codebase-bugfix-preflight-failed-and-reporter-fixed"
        )
        assert len(data["feature_id"]) <= 64

    def test_multiple_slugs_is_order_independent(self):
        result_a = _run([
            "derive-feature-id",
            "--slugs",
            "z-last-bug",
            "a-first-bug",
            "m-middle-bug",
        ])
        result_b = _run([
            "derive-feature-id",
            "--slugs",
            "m-middle-bug",
            "z-last-bug",
            "a-first-bug",
        ])
        assert result_a.returncode == 0
        assert result_b.returncode == 0
        data_a = json.loads(result_a.stdout.strip())
        data_b = json.loads(result_b.stdout.strip())
        assert data_a["stub"] == "a-first-bug-batch-3"
        assert data_a["feature_id"] == "lens-dev-new-codebase-bugfix-a-first-bug-batch-3"
        assert data_a["feature_id"] == data_b["feature_id"]

    def test_requires_non_empty_slug_list(self):
        result = _run(["derive-feature-id"])
        assert result.returncode == 1
        assert "At least one non-empty slug is required" in result.stderr


# ---------------------------------------------------------------------------
# move-to-inprogress
# ---------------------------------------------------------------------------


class TestMoveToInprogress:
    def test_moves_bug_from_new_to_inprogress(self, tmp_path):
        governance_repo = tmp_path / "gov"
        bugs_new = governance_repo / "bugs" / "New"
        _make_bug_file(bugs_new, "test-slug-aabb1122", status="New")
        result = _run([
            "move-to-inprogress",
            "--governance-repo", str(governance_repo),
            "--feature-id", "lens-dev-new-codebase-bugfix-test",
            "--slugs", "test-slug-aabb1122",
        ])
        assert result.returncode == 0
        data = json.loads(result.stdout.strip())
        assert "test-slug-aabb1122" in data["moved"]
        assert data["failed"] == []
        # source is gone, dest exists
        assert not (governance_repo / "bugs" / "New" / "test-slug-aabb1122.md").exists()
        dest = governance_repo / "bugs" / "Inprogress" / "test-slug-aabb1122.md"
        assert dest.exists()

    def test_frontmatter_updated_on_inprogress_move(self, tmp_path):
        governance_repo = tmp_path / "gov"
        bugs_new = governance_repo / "bugs" / "New"
        _make_bug_file(bugs_new, "slug-fronty-cc334455", status="New")
        _run([
            "move-to-inprogress",
            "--governance-repo", str(governance_repo),
            "--feature-id", "lens-dev-new-codebase-bugfix-test",
            "--slugs", "slug-fronty-cc334455",
        ])
        dest = governance_repo / "bugs" / "Inprogress" / "slug-fronty-cc334455.md"
        content = dest.read_text(encoding="utf-8")
        assert "Inprogress" in content
        assert "lens-dev-new-codebase-bugfix-test" in content

    def test_missing_slug_reported_in_failed(self, tmp_path):
        governance_repo = tmp_path / "gov"
        governance_repo.mkdir()
        result = _run([
            "move-to-inprogress",
            "--governance-repo", str(governance_repo),
            "--feature-id", "lens-dev-new-codebase-bugfix-test",
            "--slugs", "nonexistent-slug",
        ])
        assert result.returncode == 0
        data = json.loads(result.stdout.strip())
        assert "nonexistent-slug" in [f["slug"] for f in data["failed"]]
        assert data["moved"] == []

    def test_exits_1_when_governance_repo_missing(self):
        with tempfile.TemporaryDirectory() as td:
            missing = Path(td) / "does-not-exist"
        result = _run([
            "move-to-inprogress",
            "--governance-repo", str(missing),
            "--feature-id", "lens-dev-new-codebase-bugfix-test",
            "--slugs", "any-slug",
        ])
        assert result.returncode == 1

    def test_exits_1_when_feature_id_empty(self, tmp_path):
        governance_repo = tmp_path / "gov"
        governance_repo.mkdir()
        result = _run([
            "move-to-inprogress",
            "--governance-repo", str(governance_repo),
            "--feature-id", "",
            "--slugs", "any-slug",
        ])
        assert result.returncode == 1

    def test_rejects_legacy_random_feature_id(self, tmp_path):
        governance_repo = tmp_path / "gov"
        bugs_new = governance_repo / "bugs" / "New"
        _make_bug_file(bugs_new, "slug-random-reject-1122", status="New")
        result = _run([
            "move-to-inprogress",
            "--governance-repo", str(governance_repo),
            "--feature-id", "lens-dev-new-codebase-bugfix-1777828805636-46cf",
            "--slugs", "slug-random-reject-1122",
        ])
        assert result.returncode == 1
        assert "deprecated random timestamp/hex suffix" in result.stderr


# ---------------------------------------------------------------------------
# move-to-fixed
# ---------------------------------------------------------------------------


class TestMoveToFixed:
    def test_moves_bug_from_inprogress_to_fixed(self, tmp_path):
        governance_repo = tmp_path / "gov"
        bugs_ip = governance_repo / "bugs" / "Inprogress"
        _make_bug_file(bugs_ip, "ip-slug-ffgg8899", status="Inprogress", feature_id="lens-dev-new-codebase-bugfix-test")
        result = _run([
            "move-to-fixed",
            "--governance-repo", str(governance_repo),
            "--slugs", "ip-slug-ffgg8899",
        ])
        assert result.returncode == 0
        data = json.loads(result.stdout.strip())
        assert "ip-slug-ffgg8899" in data["moved"]
        assert data["failed"] == []
        assert not (governance_repo / "bugs" / "Inprogress" / "ip-slug-ffgg8899.md").exists()
        dest = governance_repo / "bugs" / "Fixed" / "ip-slug-ffgg8899.md"
        assert dest.exists()

    def test_frontmatter_updated_on_fixed_move(self, tmp_path):
        governance_repo = tmp_path / "gov"
        bugs_ip = governance_repo / "bugs" / "Inprogress"
        _make_bug_file(bugs_ip, "slug-fixfm-aabb", status="Inprogress")
        _run([
            "move-to-fixed",
            "--governance-repo", str(governance_repo),
            "--slugs", "slug-fixfm-aabb",
        ])
        dest = governance_repo / "bugs" / "Fixed" / "slug-fixfm-aabb.md"
        content = dest.read_text(encoding="utf-8")
        assert "Fixed" in content

    def test_missing_inprogress_slug_reported_in_failed(self, tmp_path):
        governance_repo = tmp_path / "gov"
        governance_repo.mkdir()
        result = _run([
            "move-to-fixed",
            "--governance-repo", str(governance_repo),
            "--slugs", "missing-ip-slug",
        ])
        assert result.returncode == 0
        data = json.loads(result.stdout.strip())
        assert "missing-ip-slug" in [f["slug"] for f in data["failed"]]

    def test_exits_1_when_governance_repo_missing(self):
        with tempfile.TemporaryDirectory() as td:
            missing = Path(td) / "does-not-exist"
        result = _run([
            "move-to-fixed",
            "--governance-repo", str(missing),
            "--slugs", "any-slug",
        ])
        assert result.returncode == 1


# ---------------------------------------------------------------------------
# resolve-bugs
# ---------------------------------------------------------------------------


class TestResolveBugs:
    def test_resolve_finds_inprogress_bugs_by_feature_id(self, tmp_path):
        governance_repo = tmp_path / "gov"
        bugs_ip = governance_repo / "bugs" / "Inprogress"
        _make_bug_file(bugs_ip, "res-slug-aa1122bb", status="Inprogress",
                       feature_id="lens-dev-new-codebase-bugfix-resolve")
        result = _run([
            "resolve-bugs",
            "--governance-repo", str(governance_repo),
            "--feature-id", "lens-dev-new-codebase-bugfix-resolve",
        ])
        assert result.returncode == 0
        data = json.loads(result.stdout.strip())
        assert "res-slug-aa1122bb" in data["resolved"]

    def test_resolve_returns_error_when_no_bugs_found(self, tmp_path):
        governance_repo = tmp_path / "gov"
        governance_repo.mkdir()
        result = _run([
            "resolve-bugs",
            "--governance-repo", str(governance_repo),
            "--feature-id", "lens-dev-new-codebase-bugfix-nonexistent",
        ])
        assert result.returncode == 1

    def test_resolve_exits_1_when_governance_repo_missing(self):
        with tempfile.TemporaryDirectory() as td:
            missing = Path(td) / "does-not-exist"
        result = _run([
            "resolve-bugs",
            "--governance-repo", str(missing),
            "--feature-id", "lens-dev-new-codebase-bugfix-x",
        ])
        assert result.returncode == 1

    def test_resolve_reports_already_fixed(self, tmp_path):
        governance_repo = tmp_path / "gov"
        bugs_fixed = governance_repo / "bugs" / "Fixed"
        _make_bug_file(bugs_fixed, "fixed-slug-cc4455dd", status="Fixed",
                       feature_id="lens-dev-new-codebase-bugfix-done")
        result = _run([
            "resolve-bugs",
            "--governance-repo", str(governance_repo),
            "--feature-id", "lens-dev-new-codebase-bugfix-done",
        ])
        # Returns 0 because already_fixed is non-empty
        assert result.returncode == 0
        data = json.loads(result.stdout.strip())
        assert "fixed-slug-cc4455dd" in data["already_fixed"]

    def test_resolve_rejects_invalid_feature_id_format(self, tmp_path):
        governance_repo = tmp_path / "gov"
        governance_repo.mkdir()
        result = _run([
            "resolve-bugs",
            "--governance-repo", str(governance_repo),
            "--feature-id", "bugfix-plain-invalid",
        ])
        assert result.returncode == 1
        assert "must start with 'lens-dev-new-codebase-bugfix-'" in result.stderr


# ---------------------------------------------------------------------------
# derive-feature-id — regression: stub must fit within SAFE_ID_PATTERN (max 64 chars)
# ---------------------------------------------------------------------------


class TestDeriveFeatureIdLengthConstraint:
    """Regression tests for story 2.1: derive-feature-id stub truncation fix."""

    def test_derive_feature_id_respects_max_length(self):
        """Feature ID must never exceed 64 chars regardless of input slug length."""
        long_slug = "a-very-long-bugfix-description-that-exceeds-thirty-five-characters-easily"
        result = _run(["derive-feature-id", "--slugs", long_slug])
        assert result.returncode == 0
        data = json.loads(result.stdout.strip())
        feature_id = data["feature_id"]
        assert len(feature_id) <= 64, (
            f"Feature ID too long: {len(feature_id)} chars — '{feature_id}'"
        )

    def test_derive_feature_id_single_short_slug_preserved(self):
        """Short slugs should not be truncated."""
        result = _run(["derive-feature-id", "--slugs", "short-slug"])
        assert result.returncode == 0
        data = json.loads(result.stdout.strip())
        assert data["feature_id"] == "lens-dev-new-codebase-bugfix-short-slug"

    def test_derive_feature_id_batch_max_length(self):
        """Batch stub from multiple long slugs must also fit within 64 chars."""
        slugs = [
            "extremely-long-first-slug-with-many-words",
            "another-very-long-second-slug-here",
        ]
        result = _run(["derive-feature-id", "--slugs", *slugs])
        assert result.returncode == 0
        data = json.loads(result.stdout.strip())
        feature_id = data["feature_id"]
        assert len(feature_id) <= 64, (
            f"Batch feature ID too long: {len(feature_id)} chars — '{feature_id}'"
        )
