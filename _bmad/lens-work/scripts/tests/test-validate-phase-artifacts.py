"""Tests for validate-phase-artifacts.py story-file compatibility."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).parent.parent / "validate-phase-artifacts.py"
LIFECYCLE = Path(__file__).parent.parent.parent / "lifecycle.yaml"


def _run(*args: str):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
    )


def _make_docs(tmp_path: Path) -> Path:
    docs_root = tmp_path / "docs"
    docs_root.mkdir()
    (docs_root / "finalizeplan-review.md").write_text("# Review\n", encoding="utf-8")
    (docs_root / "epics.md").write_text("# Epics\n", encoding="utf-8")
    (docs_root / "stories.md").write_text("# Stories\n", encoding="utf-8")
    (docs_root / "implementation-readiness.md").write_text("# Ready\n", encoding="utf-8")
    (docs_root / "sprint-status.yaml").write_text("status: draft\n", encoding="utf-8")
    return docs_root


def _story_frontmatter(story_id: str = "PF-1.1") -> str:
    return f"""---
feature: lens-dev-new-codebase-preandpostflight
story_id: "{story_id}"
doc_type: story
status: ready-for-dev
title: "Metadata-ready story"
depends_on: []
updated_at: 2026-05-04T00:00:00Z
---

# Story {story_id}: Metadata-ready story
"""


class TestValidatePhaseArtifactsStoryFiles:
    def test_ignores_batch_input_files_for_phase_completion(self, tmp_path):
        docs_root = _make_docs(tmp_path)
        (docs_root / "techplan-batch-input.md").write_text("# Batch Input\n", encoding="utf-8")

        result = _run(
            "--phase", "techplan",
            "--lifecycle-path", str(LIFECYCLE),
            "--docs-root", str(docs_root),
            "--json",
        )

        assert result.returncode == 1, result.stdout + result.stderr
        payload = json.loads(result.stdout)
        assert payload["status"] == "fail"
        assert payload["missing"] == ["architecture"]

    def test_accepts_root_story_key_files(self, tmp_path):
        docs_root = _make_docs(tmp_path)
        (docs_root / "1-2-user-auth.md").write_text("# Story\n", encoding="utf-8")

        result = _run(
            "--phase", "finalizeplan",
            "--lifecycle-path", str(LIFECYCLE),
            "--docs-root", str(docs_root),
            "--json",
        )

        assert result.returncode == 0, result.stdout + result.stderr
        payload = json.loads(result.stdout)
        assert payload["status"] == "pass"

    def test_accepts_stories_subdir_files(self, tmp_path):
        docs_root = _make_docs(tmp_path)
        stories_dir = docs_root / "stories"
        stories_dir.mkdir()
        (stories_dir / "1-3-admin-audit.yaml").write_text("status: ready-for-dev\n", encoding="utf-8")

        result = _run(
            "--phase", "finalizeplan",
            "--lifecycle-path", str(LIFECYCLE),
            "--docs-root", str(docs_root),
            "--json",
        )

        assert result.returncode == 0, result.stdout + result.stderr
        payload = json.loads(result.stdout)
        assert payload["status"] == "pass"

    def test_accepts_legacy_dev_story_files(self, tmp_path):
        docs_root = _make_docs(tmp_path)
        (docs_root / "dev-story-1-4-payments.md").write_text("# Legacy Story\n", encoding="utf-8")

        result = _run(
            "--phase", "finalizeplan",
            "--lifecycle-path", str(LIFECYCLE),
            "--docs-root", str(docs_root),
            "--json",
        )

        assert result.returncode == 0, result.stdout + result.stderr
        payload = json.loads(result.stdout)
        assert payload["status"] == "pass"

    def test_strict_metadata_requires_story_frontmatter(self, tmp_path):
        docs_root = _make_docs(tmp_path)
        stories_dir = docs_root / "stories"
        stories_dir.mkdir()
        (stories_dir / "story-PF-1.1.md").write_text("# Story PF-1.1\n", encoding="utf-8")

        result = _run(
            "--phase", "finalizeplan",
            "--lifecycle-path", str(LIFECYCLE),
            "--docs-root", str(docs_root),
            "--strict-metadata",
            "--json",
        )

        assert result.returncode == 1, result.stdout + result.stderr
        payload = json.loads(result.stdout)
        assert payload["status"] == "fail"
        assert payload["failure_reason"] == "metadata_errors"
        assert "story-PF-1.1.md missing story frontmatter fields" in payload["metadata_errors"][0]

    def test_strict_metadata_accepts_story_frontmatter(self, tmp_path):
        docs_root = _make_docs(tmp_path)
        stories_dir = docs_root / "stories"
        stories_dir.mkdir()
        (stories_dir / "story-PF-1.1.md").write_text(_story_frontmatter(), encoding="utf-8")

        result = _run(
            "--phase", "finalizeplan",
            "--lifecycle-path", str(LIFECYCLE),
            "--docs-root", str(docs_root),
            "--strict-metadata",
            "--json",
        )

        assert result.returncode == 0, result.stdout + result.stderr
        payload = json.loads(result.stdout)
        assert payload["status"] == "pass"
        assert payload["metadata_errors"] == []

    def test_strict_metadata_rejects_missing_story_file_referenced_by_sprint_status(self, tmp_path):
        docs_root = _make_docs(tmp_path)
        (docs_root / "sprint-status.yaml").write_text(
            """
sprints:
  - sprint_number: 1
    stories:
      - story_id: PF-1.1
        status: ready-for-dev
      - story_id: PF-1.2
        status: ready-for-dev
""".lstrip(),
            encoding="utf-8",
        )
        stories_dir = docs_root / "stories"
        stories_dir.mkdir()
        (stories_dir / "story-PF-1.1.md").write_text(_story_frontmatter("PF-1.1"), encoding="utf-8")

        result = _run(
            "--phase", "finalizeplan",
            "--lifecycle-path", str(LIFECYCLE),
            "--docs-root", str(docs_root),
            "--strict-metadata",
            "--json",
        )

        assert result.returncode == 1, result.stdout + result.stderr
        payload = json.loads(result.stdout)
        assert payload["status"] == "fail"
        assert payload["failure_reason"] == "metadata_errors"
        assert payload["metadata_errors"] == [
            "sprint-status.yaml references story IDs without matching story files: PF-1.2"
        ]

    def test_strict_metadata_accepts_all_sprint_status_story_files(self, tmp_path):
        docs_root = _make_docs(tmp_path)
        (docs_root / "sprint-status.yaml").write_text(
            """
sprints:
  - sprint_number: 1
    stories:
      - story_id: PF-1.1
        status: ready-for-dev
      - story_id: PF-1.2
        status: ready-for-dev
""".lstrip(),
            encoding="utf-8",
        )
        stories_dir = docs_root / "stories"
        stories_dir.mkdir()
        (stories_dir / "story-PF-1.1.md").write_text(_story_frontmatter("PF-1.1"), encoding="utf-8")
        (stories_dir / "story-PF-1.2.md").write_text(_story_frontmatter("PF-1.2"), encoding="utf-8")

        result = _run(
            "--phase", "finalizeplan",
            "--lifecycle-path", str(LIFECYCLE),
            "--docs-root", str(docs_root),
            "--strict-metadata",
            "--json",
        )

        assert result.returncode == 0, result.stdout + result.stderr
        payload = json.loads(result.stdout)
        assert payload["status"] == "pass"
        assert payload["metadata_errors"] == []

    def test_strict_metadata_requires_sprint_status_yaml_for_story_coverage(self, tmp_path):
        docs_root = _make_docs(tmp_path)
        (docs_root / "sprint-status.yaml").unlink()
        (docs_root / "sprint-backlog.md").write_text("# Sprint Backlog\n", encoding="utf-8")
        stories_dir = docs_root / "stories"
        stories_dir.mkdir()
        (stories_dir / "story-PF-1.1.md").write_text(_story_frontmatter("PF-1.1"), encoding="utf-8")

        result = _run(
            "--phase", "finalizeplan",
            "--lifecycle-path", str(LIFECYCLE),
            "--docs-root", str(docs_root),
            "--strict-metadata",
            "--json",
        )

        assert result.returncode == 1, result.stdout + result.stderr
        payload = json.loads(result.stdout)
        assert payload["status"] == "fail"
        assert payload["failure_reason"] == "metadata_errors"
        assert payload["metadata_errors"] == [
            "strict metadata requires sprint-status.yaml to verify story-file coverage; "
            "sprint-backlog.md alone is insufficient"
        ]

    def test_strict_metadata_rejects_draft_sprint_plan(self, tmp_path):
        docs_root = _make_docs(tmp_path)
        stories_dir = docs_root / "stories"
        stories_dir.mkdir()
        (stories_dir / "story-PF-1.1.md").write_text(_story_frontmatter(), encoding="utf-8")
        (docs_root / "sprint-plan.md").write_text(
            """---
feature: lens-dev-new-codebase-preandpostflight
doc_type: sprint-plan
status: draft
open_questions:
  - Which metadata should be updated?
---

# Sprint Plan
""",
            encoding="utf-8",
        )

        result = _run(
            "--phase", "finalizeplan",
            "--lifecycle-path", str(LIFECYCLE),
            "--docs-root", str(docs_root),
            "--strict-metadata",
            "--json",
        )

        assert result.returncode == 1, result.stdout + result.stderr
        payload = json.loads(result.stdout)
        assert payload["status"] == "fail"
        assert any(error.startswith("sprint-plan.md status is draft") for error in payload["metadata_errors"])
        assert "sprint-plan.md has unresolved open_questions" in payload["metadata_errors"]

    def test_strict_metadata_rejects_malformed_story_yaml(self, tmp_path):
        docs_root = _make_docs(tmp_path)
        stories_dir = docs_root / "stories"
        stories_dir.mkdir()
        (stories_dir / "story-PF-1.1.md").write_text(
            "---\nbad: [unclosed bracket\n---\n# Story\n", encoding="utf-8"
        )

        result = _run(
            "--phase", "finalizeplan",
            "--lifecycle-path", str(LIFECYCLE),
            "--docs-root", str(docs_root),
            "--strict-metadata",
            "--json",
        )

        assert result.returncode == 1, result.stdout + result.stderr
        payload = json.loads(result.stdout)
        assert payload["status"] == "fail"
        assert payload["failure_reason"] == "metadata_errors"
        assert any("malformed YAML frontmatter" in e for e in payload["metadata_errors"])

    def test_strict_metadata_rejects_malformed_sprint_plan_yaml(self, tmp_path):
        docs_root = _make_docs(tmp_path)
        stories_dir = docs_root / "stories"
        stories_dir.mkdir()
        (stories_dir / "story-PF-1.1.md").write_text(_story_frontmatter(), encoding="utf-8")
        (docs_root / "sprint-plan.md").write_text(
            "---\nbad: [unclosed bracket\n---\n# Sprint Plan\n", encoding="utf-8"
        )

        result = _run(
            "--phase", "finalizeplan",
            "--lifecycle-path", str(LIFECYCLE),
            "--docs-root", str(docs_root),
            "--strict-metadata",
            "--json",
        )

        assert result.returncode == 1, result.stdout + result.stderr
        payload = json.loads(result.stdout)
        assert payload["status"] == "fail"
        assert payload["failure_reason"] == "metadata_errors"
        assert "sprint-plan.md has malformed YAML frontmatter (parse error)" in payload["metadata_errors"]

    def test_completion_review_contract_checks_only_review_inputs(self, tmp_path):
        docs_root = tmp_path / "docs"
        docs_root.mkdir()
        (docs_root / "business-plan.md").write_text("# Business\n", encoding="utf-8")
        (docs_root / "tech-plan.md").write_text("# Tech\n", encoding="utf-8")

        result = _run(
            "--phase", "expressplan",
            "--contract", "completion-review",
            "--lifecycle-path", str(LIFECYCLE),
            "--docs-root", str(docs_root),
            "--json",
        )

        assert result.returncode == 0, result.stdout + result.stderr
        payload = json.loads(result.stdout)
        assert payload["contract"] == "completion-review"
        assert payload["status"] == "pass"

    def test_review_ready_contract_requires_pre_review_outputs(self, tmp_path):
        docs_root = tmp_path / "docs"
        docs_root.mkdir()
        (docs_root / "business-plan.md").write_text("# Business\n", encoding="utf-8")
        (docs_root / "tech-plan.md").write_text("# Tech\n", encoding="utf-8")

        result = _run(
            "--phase", "expressplan",
            "--contract", "review-ready",
            "--lifecycle-path", str(LIFECYCLE),
            "--docs-root", str(docs_root),
            "--json",
        )

        assert result.returncode == 1, result.stdout + result.stderr
        payload = json.loads(result.stdout)
        assert payload["contract"] == "review-ready"
        assert payload["status"] == "fail"
        assert payload["missing"] == ["sprint-plan"]

    def test_review_ready_contract_accepts_all_pre_review_outputs(self, tmp_path):
        docs_root = tmp_path / "docs"
        docs_root.mkdir()
        (docs_root / "business-plan.md").write_text("# Business\n", encoding="utf-8")
        (docs_root / "tech-plan.md").write_text("# Tech\n", encoding="utf-8")
        (docs_root / "sprint-plan.md").write_text("# Sprint\n", encoding="utf-8")

        result = _run(
            "--phase", "expressplan",
            "--contract", "review-ready",
            "--lifecycle-path", str(LIFECYCLE),
            "--docs-root", str(docs_root),
            "--json",
        )

        assert result.returncode == 0, result.stdout + result.stderr
        payload = json.loads(result.stdout)
        assert payload["contract"] == "review-ready"
        assert payload["status"] == "pass"

    def test_phase_artifacts_accepts_legacy_express_review_alias(self, tmp_path):
        docs_root = tmp_path / "docs"
        docs_root.mkdir()
        (docs_root / "business-plan.md").write_text("# Business\n", encoding="utf-8")
        (docs_root / "tech-plan.md").write_text("# Tech\n", encoding="utf-8")
        (docs_root / "sprint-plan.md").write_text("# Sprint\n", encoding="utf-8")
        (docs_root / "expressplan-review.md").write_text("# Legacy Review\n", encoding="utf-8")

        result = _run(
            "--phase", "expressplan",
            "--contract", "phase-artifacts",
            "--lifecycle-path", str(LIFECYCLE),
            "--docs-root", str(docs_root),
            "--json",
        )

        assert result.returncode == 0, result.stdout + result.stderr
        payload = json.loads(result.stdout)
        assert payload["status"] == "pass"
        assert "expressplan-adversarial-review" in payload["found_list"]

    def test_input_ready_contract_for_finalizeplan_express_track(self, tmp_path):
        docs_root = tmp_path / "docs"
        docs_root.mkdir()
        (docs_root / "business-plan.md").write_text("# Business\n", encoding="utf-8")
        (docs_root / "tech-plan.md").write_text("# Tech\n", encoding="utf-8")
        (docs_root / "sprint-plan.md").write_text("# Sprint\n", encoding="utf-8")

        result = _run(
            "--phase", "finalizeplan",
            "--contract", "input-ready",
            "--track", "express",
            "--lifecycle-path", str(LIFECYCLE),
            "--docs-root", str(docs_root),
            "--json",
        )

        assert result.returncode == 0, result.stdout + result.stderr
        payload = json.loads(result.stdout)
        assert payload["status"] == "pass"
        assert payload["found_list"] == ["business-plan", "tech-plan", "sprint-plan"]
        assert payload["missing"] == []
        assert payload["found_files"] == {
            "business-plan": ["business-plan.md"],
            "tech-plan": ["tech-plan.md"],
            "sprint-plan": ["sprint-plan.md"],
        }

    def test_input_ready_contract_for_finalizeplan_expressplan_alias(self, tmp_path):
        docs_root = tmp_path / "docs"
        docs_root.mkdir()
        (docs_root / "business-plan.md").write_text("# Business\n", encoding="utf-8")
        (docs_root / "tech-plan.md").write_text("# Tech\n", encoding="utf-8")
        (docs_root / "sprint-plan.md").write_text("# Sprint\n", encoding="utf-8")

        result = _run(
            "--phase", "finalizeplan",
            "--contract", "input-ready",
            "--track", "expressplan",
            "--lifecycle-path", str(LIFECYCLE),
            "--docs-root", str(docs_root),
            "--json",
        )

        assert result.returncode == 0, result.stdout + result.stderr
        payload = json.loads(result.stdout)
        assert payload["status"] == "pass"
        assert payload["found_list"] == ["business-plan", "tech-plan", "sprint-plan"]

    def test_input_ready_contract_for_finalizeplan_quickplan_alias(self, tmp_path):
        docs_root = tmp_path / "docs"
        docs_root.mkdir()
        (docs_root / "business-plan.md").write_text("# Business\n", encoding="utf-8")
        (docs_root / "tech-plan.md").write_text("# Tech\n", encoding="utf-8")
        (docs_root / "sprint-plan.md").write_text("# Sprint\n", encoding="utf-8")

        result = _run(
            "--phase", "finalizeplan",
            "--contract", "input-ready",
            "--track", "quickplan",
            "--lifecycle-path", str(LIFECYCLE),
            "--docs-root", str(docs_root),
            "--json",
        )

        assert result.returncode == 0, result.stdout + result.stderr
        payload = json.loads(result.stdout)
        assert payload["status"] == "pass"
        assert payload["found_list"] == ["business-plan", "tech-plan", "sprint-plan"]

    def test_input_ready_contract_for_finalizeplan_full_requires_full_track_docs(self, tmp_path):
        docs_root = tmp_path / "docs"
        docs_root.mkdir()
        (docs_root / "business-plan.md").write_text("# Business\n", encoding="utf-8")
        (docs_root / "tech-plan.md").write_text("# Tech\n", encoding="utf-8")
        (docs_root / "sprint-plan.md").write_text("# Sprint\n", encoding="utf-8")

        result = _run(
            "--phase", "finalizeplan",
            "--contract", "input-ready",
            "--track", "full",
            "--lifecycle-path", str(LIFECYCLE),
            "--docs-root", str(docs_root),
            "--json",
        )

        assert result.returncode == 1, result.stdout + result.stderr
        payload = json.loads(result.stdout)
        assert payload["status"] == "fail"
        assert payload["failure_reason"] == "missing_artifacts"
        assert payload["missing"] == [
            "product-brief",
            "research",
            "brainstorm",
            "prd",
            "ux-design",
            "architecture",
        ]

    def test_input_ready_contract_for_finalizeplan_unknown_track_fails(self, tmp_path):
        docs_root = tmp_path / "docs"
        docs_root.mkdir()

        result = _run(
            "--phase", "finalizeplan",
            "--contract", "input-ready",
            "--track", "unknown-track",
            "--lifecycle-path", str(LIFECYCLE),
            "--docs-root", str(docs_root),
            "--json",
        )

        assert result.returncode == 1, result.stdout + result.stderr
        payload = json.loads(result.stdout)
        assert payload["status"] == "fail"
        assert payload["failure_reason"] == "unknown_contract"
        assert "unknown-track" in payload["error"]

    def test_input_ready_contract_for_finalizeplan_requires_track(self, tmp_path):
        docs_root = tmp_path / "docs"
        docs_root.mkdir()

        result = _run(
            "--phase", "finalizeplan",
            "--contract", "input-ready",
            "--lifecycle-path", str(LIFECYCLE),
            "--docs-root", str(docs_root),
            "--json",
        )

        assert result.returncode == 1, result.stdout + result.stderr
        payload = json.loads(result.stdout)
        assert payload["status"] == "fail"
        assert payload["failure_reason"] == "unknown_contract"
        assert "--track is required" in payload["error"]

    def test_accepts_research_documents_in_research_subdir(self, tmp_path):
        docs_root = tmp_path / "docs"
        docs_root.mkdir()
        (docs_root / "product-brief.md").write_text("# Brief\n", encoding="utf-8")
        (docs_root / "brainstorm.md").write_text("# Brainstorm\n", encoding="utf-8")
        research_dir = docs_root / "research"
        research_dir.mkdir()
        (research_dir / "technical-auth-research-2026-04-14.md").write_text("# Research\n", encoding="utf-8")

        result = _run(
            "--phase", "preplan",
            "--contract", "review-ready",
            "--lifecycle-path", str(LIFECYCLE),
            "--docs-root", str(docs_root),
            "--json",
        )

        assert result.returncode == 0, result.stdout + result.stderr
        payload = json.loads(result.stdout)
        assert payload["status"] == "pass"
        assert payload["misplaced"] == {}

    def test_reports_missing_artifacts_when_docs_root_is_empty(self, tmp_path):
        docs_root = tmp_path / "feature-docs"
        docs_root.mkdir()

        result = _run(
            "--phase", "preplan",
            "--contract", "review-ready",
            "--lifecycle-path", str(LIFECYCLE),
            "--docs-root", str(docs_root),
            "--json",
        )

        assert result.returncode == 1, result.stdout + result.stderr
        payload = json.loads(result.stdout)
        assert payload["status"] == "fail"
        assert payload["failure_reason"] == "missing_artifacts"
        assert payload["missing"] == ["product-brief", "research", "brainstorm"]
        assert payload["misplaced"] == {}

    def test_reports_missing_businessplan_artifacts_when_docs_root_is_empty(self, tmp_path):
        docs_root = tmp_path / "feature-docs"
        docs_root.mkdir()

        result = _run(
            "--phase", "businessplan",
            "--contract", "review-ready",
            "--lifecycle-path", str(LIFECYCLE),
            "--docs-root", str(docs_root),
            "--json",
        )

        assert result.returncode == 1, result.stdout + result.stderr
        payload = json.loads(result.stdout)
        assert payload["status"] == "fail"
        assert payload["failure_reason"] == "missing_artifacts"
        assert payload["missing"] == ["prd", "ux-design"]
        assert payload["misplaced"] == {}
