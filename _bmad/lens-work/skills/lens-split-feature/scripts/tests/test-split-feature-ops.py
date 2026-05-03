#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest>=8.0", "pyyaml>=6.0"]
# ///
"""Split-feature regression tests covering the approved clean-room contract."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


TEST_FILE = Path(__file__).resolve()
SKILL_ROOT = TEST_FILE.parents[2]
SCRIPT = SKILL_ROOT / "scripts" / "split-feature-ops.py"


def load_module():
    spec = importlib.util.spec_from_file_location("split_feature_ops", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


split_feature_ops = load_module()


def run_script(args: list[str]) -> tuple[dict, int]:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:  # pragma: no cover
        raise AssertionError(f"Non-JSON output\nstdout={result.stdout}\nstderr={result.stderr}") from exc
    return payload, result.returncode


def write_yaml(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


def write_feature_index(governance_repo: Path, features: list[dict]) -> None:
    write_yaml(governance_repo / "feature-index.yaml", {"features": features})


def make_feature_tree(governance_repo: Path, domain: str, service: str, feature_id: str) -> Path:
    feature_dir = governance_repo / "features" / domain / service / feature_id
    (feature_dir / "stories").mkdir(parents=True, exist_ok=True)
    return feature_dir


def make_story_file(directory: Path, story_id: str, status: str, *, suffix: str = ".md", name: str | None = None) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    file_name = name or f"{story_id}{suffix}"
    story_path = directory / file_name
    if suffix in {".yaml", ".yml"}:
        write_yaml(story_path, {"story_id": story_id, "status": status, "title": f"Story {story_id}"})
    else:
        story_path.write_text(
            f"---\nstory_id: {story_id}\nstatus: {status}\ntitle: Story {story_id}\n---\n\n# {story_id}\n",
            encoding="utf-8",
        )
    return story_path


def make_sprint_plan(path: Path, statuses: dict[str, str]) -> Path:
    lines = ["# Sprint Plan", "", "```yaml", "development_status:"]
    lines.extend(f"  {story_id}: {status}" for story_id, status in statuses.items())
    lines.append("```")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def make_list_format_sprint_plan(path: Path, stories: list[dict[str, str]]) -> Path:
    path.write_text(yaml.safe_dump({"stories": stories}, sort_keys=False), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("raw_status", "expected"),
    [
        ("In Progress", "in-progress"),
        ("ready_for_dev", "ready-for-dev"),
        ("  QA Review  ", "qa-review"),
    ],
)
def test_normalize_status_rewrites_case_spaces_and_underscores(raw_status: str, expected: str):
    assert split_feature_ops.normalize_status(raw_status) == expected


def test_extract_statuses_supports_list_format_story_entries():
    payload = split_feature_ops._extract_statuses_from_yaml_str(
        """
stories:
  - id: story-1
    status: In Progress
  - story-2:
      status: ready_for_dev
  - story-3: done
"""
    )

    assert payload == {
        "story-1": "in-progress",
        "story-2": "ready-for-dev",
        "story-3": "done",
    }


@pytest.mark.parametrize("raw_status", ["in_progress", "IN_PROGRESS", "in progress"])
def test_validate_split_blocks_normalized_status_variants(tmp_path: Path, raw_status: str):
    sprint_plan = make_list_format_sprint_plan(
        tmp_path / "sprint-status.yaml",
        [
            {"id": "story-wip", "status": raw_status},
            {"id": "story-ok", "status": "done"},
        ],
    )

    payload, code = run_script([
        "validate-split",
        "--sprint-plan-file",
        str(sprint_plan),
        "--story-ids",
        "story-wip,story-ok",
    ])

    assert code == 1
    assert payload["error"] == "in_progress_stories"
    assert payload["blockers"] == ["story-wip"]
    assert payload["eligible"] == ["story-ok"]


def test_validate_split_supports_markdown_embedded_yaml(tmp_path: Path):
    sprint_plan = tmp_path / "sprint-plan.md"
    sprint_plan.write_text(
        "# Sprint Plan\n\n```yaml\nstories:\n  story-a:\n    status: pending\n  story-b:\n    status: in-progress\n```\n",
        encoding="utf-8",
    )

    payload, code = run_script([
        "validate-split",
        "--sprint-plan-file",
        str(sprint_plan),
        "--story-ids",
        "story-a,story-b",
    ])

    assert code == 1
    assert payload["blockers"] == ["story-b"]
    assert payload["eligible"] == ["story-a"]


def test_validate_split_supports_inline_key_value_format(tmp_path: Path):
    sprint_plan = tmp_path / "sprint-plan.txt"
    sprint_plan.write_text("story-a: pending\nstory-b: done\n", encoding="utf-8")

    payload, code = run_script([
        "validate-split",
        "--sprint-plan-file",
        str(sprint_plan),
        "--story-ids",
        '["story-a", "story-b"]',
    ])

    assert code == 0
    assert payload["status"] == "pass"
    assert payload["eligible"] == ["story-a", "story-b"]


def test_validate_split_passes_when_list_format_has_no_in_progress(tmp_path: Path):
    sprint_plan = make_list_format_sprint_plan(
        tmp_path / "sprint-status.yaml",
        [
            {"id": "story-1", "status": "pending"},
            {"id": "story-2", "status": "ready_for_dev"},
        ],
    )

    payload, code = run_script([
        "validate-split",
        "--sprint-plan-file",
        str(sprint_plan),
        "--story-ids",
        "story-1,story-2",
    ])

    assert code == 0
    assert payload == {
        "status": "pass",
        "eligible": ["story-1", "story-2"],
        "blocked": [],
        "blockers": [],
    }


def test_validate_split_falls_back_to_story_frontmatter_when_plan_unrecognized(tmp_path: Path):
    sprint_plan = tmp_path / "sprint-status.yaml"
    sprint_plan.write_text("this is not a sprint plan\n", encoding="utf-8")
    make_story_file(tmp_path, "E1-S1", "in_progress", name="E1-S1-add-status-normalization.md")
    make_story_file(tmp_path, "E1-S2", "ready", name="E1-S2-fix-duplicate-detection.md")

    payload, code = run_script([
        "validate-split",
        "--sprint-plan-file",
        str(sprint_plan),
        "--story-ids",
        "E1-S1,E1-S2",
    ])

    assert code == 1
    assert payload["blockers"] == ["E1-S1"]
    assert payload["eligible"] == ["E1-S2"]


def test_validate_split_falls_back_to_yaml_story_file_when_story_missing_from_plan(tmp_path: Path):
    sprint_plan = make_sprint_plan(tmp_path / "sprint-plan.md", {"story-ready": "pending"})
    stories_dir = tmp_path / "stories"
    make_story_file(stories_dir, "story-wip", "in progress", suffix=".yaml")

    payload, code = run_script([
        "validate-split",
        "--sprint-plan-file",
        str(sprint_plan),
        "--story-ids",
        "story-ready,story-wip",
    ])

    assert code == 1
    assert payload["blockers"] == ["story-wip"]
    assert payload["eligible"] == ["story-ready"]


def test_validate_split_sprint_plan_status_takes_precedence_over_story_file(tmp_path: Path):
    sprint_plan = make_sprint_plan(tmp_path / "sprint-plan.md", {"story-1": "done"})
    make_story_file(tmp_path, "story-1", "in-progress", name="story-1-details.md")

    payload, code = run_script([
        "validate-split",
        "--sprint-plan-file",
        str(sprint_plan),
        "--story-ids",
        "story-1",
    ])

    assert code == 0
    assert payload["status"] == "pass"
    assert payload["eligible"] == ["story-1"]


def test_create_split_feature_writes_feature_artifacts(tmp_path: Path):
    governance_repo = tmp_path / "governance"
    governance_repo.mkdir()

    payload, code = run_script([
        "create-split-feature",
        "--governance-repo",
        str(governance_repo),
        "--source-feature-id",
        "auth-login",
        "--source-domain",
        "platform",
        "--source-service",
        "identity",
        "--new-feature-id",
        "auth-mfa",
        "--new-name",
        "MFA Authentication",
        "--track",
        "quickplan",
        "--username",
        "cweber",
    ])

    feature_dir = governance_repo / "features" / "platform" / "identity" / "auth-mfa"
    feature_yaml = yaml.safe_load((feature_dir / "feature.yaml").read_text(encoding="utf-8"))
    feature_index = yaml.safe_load((governance_repo / "feature-index.yaml").read_text(encoding="utf-8"))

    assert code == 0
    assert payload["status"] == "pass"
    assert feature_yaml["featureId"] == "auth-mfa"
    assert feature_yaml["split_from"] == "auth-login"
    assert (feature_dir / "summary.md").exists()
    assert feature_index["features"][0]["id"] == "auth-mfa"


def test_create_split_feature_dry_run_has_no_side_effects(tmp_path: Path):
    governance_repo = tmp_path / "governance"
    governance_repo.mkdir()

    payload, code = run_script([
        "create-split-feature",
        "--governance-repo",
        str(governance_repo),
        "--source-feature-id",
        "auth-login",
        "--source-domain",
        "platform",
        "--source-service",
        "identity",
        "--new-feature-id",
        "auth-mfa",
        "--new-name",
        "MFA Authentication",
        "--track",
        "quickplan",
        "--username",
        "cweber",
        "--dry-run",
    ])

    assert code == 0
    assert payload["dry_run"] is True
    assert not (governance_repo / "features").exists()
    assert not (governance_repo / "feature-index.yaml").exists()


def test_create_split_feature_fails_fast_on_duplicate_index_entry(tmp_path: Path):
    governance_repo = tmp_path / "governance"
    governance_repo.mkdir()
    write_feature_index(
        governance_repo,
        [
            {
                "id": "auth-mfa",
                "domain": "platform",
                "service": "identity",
                "status": "active",
                "owner": "cweber",
                "summary": "Existing feature",
            }
        ],
    )

    payload, code = run_script([
        "create-split-feature",
        "--governance-repo",
        str(governance_repo),
        "--source-feature-id",
        "auth-login",
        "--source-domain",
        "platform",
        "--source-service",
        "identity",
        "--new-feature-id",
        "auth-mfa",
        "--new-name",
        "MFA Authentication",
        "--track",
        "quickplan",
        "--username",
        "cweber",
    ])

    assert code == 1
    assert payload["error"] == "duplicate_feature"
    assert not (governance_repo / "features" / "platform" / "identity" / "auth-mfa").exists()


@pytest.mark.parametrize(
    ("field_flag", "value"),
    [
        ("--new-feature-id", "INVALID ID"),
        ("--source-domain", "../escape"),
    ],
)
def test_create_split_feature_rejects_invalid_identifiers(tmp_path: Path, field_flag: str, value: str):
    governance_repo = tmp_path / "governance"
    governance_repo.mkdir()
    args = [
        "create-split-feature",
        "--governance-repo",
        str(governance_repo),
        "--source-feature-id",
        "auth-login",
        "--source-domain",
        "platform",
        "--source-service",
        "identity",
        "--new-feature-id",
        "auth-mfa",
        "--new-name",
        "MFA Authentication",
        "--track",
        "quickplan",
        "--username",
        "cweber",
    ]
    index = args.index(field_flag)
    args[index + 1] = value

    payload, code = run_script(args)

    assert code == 1
    assert payload["error"] == "invalid_identifier"


@pytest.mark.parametrize("raw_status", ["in_progress", "IN_PROGRESS", "in progress"])
def test_move_stories_blocks_normalized_status_variants(tmp_path: Path, raw_status: str):
    governance_repo = tmp_path / "governance"
    source_dir = make_feature_tree(governance_repo, "platform", "identity", "auth-login")
    make_feature_tree(governance_repo, "platform", "identity", "auth-mfa")
    story_path = make_story_file(source_dir / "stories", "story-1", raw_status)

    payload, code = run_script([
        "move-stories",
        "--governance-repo",
        str(governance_repo),
        "--source-feature-id",
        "auth-login",
        "--source-domain",
        "platform",
        "--source-service",
        "identity",
        "--target-feature-id",
        "auth-mfa",
        "--target-domain",
        "platform",
        "--target-service",
        "identity",
        "--story-ids",
        "story-1",
    ])

    assert code == 1
    assert payload["error"] == "in_progress_stories"
    assert payload["blocked"][0]["id"] == "story-1"
    assert story_path.exists()


@pytest.mark.parametrize("suffix", [".md", ".yaml"])
def test_move_stories_moves_story_file_variants(tmp_path: Path, suffix: str):
    governance_repo = tmp_path / "governance"
    source_dir = make_feature_tree(governance_repo, "platform", "identity", "auth-login")
    target_dir = make_feature_tree(governance_repo, "platform", "identity", "auth-mfa")
    source_story = make_story_file(source_dir / "stories", "story-1", "pending", suffix=suffix)

    payload, code = run_script([
        "move-stories",
        "--governance-repo",
        str(governance_repo),
        "--source-feature-id",
        "auth-login",
        "--source-domain",
        "platform",
        "--source-service",
        "identity",
        "--target-feature-id",
        "auth-mfa",
        "--target-domain",
        "platform",
        "--target-service",
        "identity",
        "--story-ids",
        "story-1",
    ])

    assert code == 0
    assert payload["total_moved"] == 1
    assert not source_story.exists()
    assert (target_dir / "stories" / source_story.name).exists()


def test_move_stories_dry_run_preserves_source_files(tmp_path: Path):
    governance_repo = tmp_path / "governance"
    source_dir = make_feature_tree(governance_repo, "platform", "identity", "auth-login")
    make_feature_tree(governance_repo, "platform", "identity", "auth-mfa")
    story_path = make_story_file(source_dir / "stories", "story-3", "pending")

    payload, code = run_script([
        "move-stories",
        "--governance-repo",
        str(governance_repo),
        "--source-feature-id",
        "auth-login",
        "--source-domain",
        "platform",
        "--source-service",
        "identity",
        "--target-feature-id",
        "auth-mfa",
        "--target-domain",
        "platform",
        "--target-service",
        "identity",
        "--story-ids",
        "story-3",
        "--dry-run",
    ])

    assert code == 0
    assert payload["dry_run"] is True
    assert payload["total_moved"] == 1
    assert story_path.exists()


def test_move_stories_reports_missing_story_ids(tmp_path: Path):
    governance_repo = tmp_path / "governance"
    source_dir = make_feature_tree(governance_repo, "platform", "identity", "auth-login")
    make_feature_tree(governance_repo, "platform", "identity", "auth-mfa")
    make_story_file(source_dir / "stories", "story-present", "pending")

    payload, code = run_script([
        "move-stories",
        "--governance-repo",
        str(governance_repo),
        "--source-feature-id",
        "auth-login",
        "--source-domain",
        "platform",
        "--source-service",
        "identity",
        "--target-feature-id",
        "auth-mfa",
        "--target-domain",
        "platform",
        "--target-service",
        "identity",
        "--story-ids",
        "story-present,story-missing",
    ])

    assert code == 1
    assert payload["error"] == "stories_not_found"
    assert payload["not_found"] == ["story-missing"]
    assert payload["total_moved"] == 0


def test_move_stories_rejects_invalid_identifiers(tmp_path: Path):
    governance_repo = tmp_path / "governance"
    governance_repo.mkdir()

    payload, code = run_script([
        "move-stories",
        "--governance-repo",
        str(governance_repo),
        "--source-feature-id",
        "INVALID ID",
        "--source-domain",
        "platform",
        "--source-service",
        "identity",
        "--target-feature-id",
        "auth-mfa",
        "--target-domain",
        "platform",
        "--target-service",
        "identity",
        "--story-ids",
        "story-1",
    ])

    assert code == 1
    assert payload["error"] == "invalid_identifier"
    assert payload["total_moved"] == 0


def test_validate_split_fails_when_sprint_plan_file_missing(tmp_path: Path):
    nonexistent = tmp_path / "no-such-file.yaml"

    payload, code = run_script([
        "validate-split",
        "--sprint-plan-file",
        str(nonexistent),
        "--story-ids",
        "story-1,story-2",
    ])

    assert code == 1
    assert payload["error"] == "sprint_plan_missing"
    assert payload["eligible"] == []
    assert payload["blockers"] == []


@pytest.mark.parametrize(
    "story_id",
    ["../outside", "sub/dir", "glob*id", "query?id", "[bracket]", "absolute"],
)
def test_validate_split_rejects_unsafe_story_ids(tmp_path: Path, story_id: str):
    sprint_plan = make_sprint_plan(tmp_path / "sprint-plan.md", {"story-safe": "pending"})
    # Inject an absolute path variant for the "absolute" parametrize value
    if story_id == "absolute":
        story_id = str(tmp_path / "some-story")

    payload, code = run_script([
        "validate-split",
        "--sprint-plan-file",
        str(sprint_plan),
        "--story-ids",
        story_id,
    ])

    assert code == 1
    assert payload["error"] == "invalid_story_id"
    assert payload["eligible"] == []


def test_create_split_feature_rejects_nonexistent_governance_repo(tmp_path: Path):
    nonexistent_repo = tmp_path / "does-not-exist"

    payload, code = run_script([
        "create-split-feature",
        "--governance-repo",
        str(nonexistent_repo),
        "--source-feature-id",
        "auth-login",
        "--source-domain",
        "platform",
        "--source-service",
        "identity",
        "--new-feature-id",
        "auth-mfa",
        "--new-name",
        "MFA Authentication",
        "--track",
        "quickplan",
        "--username",
        "cweber",
    ])

    assert code == 1
    assert payload["error"] == "governance_repo_missing"


@pytest.mark.parametrize(
    "story_id",
    ["../escape", "sub/story", "glob*"],
)
def test_move_stories_rejects_unsafe_story_ids(tmp_path: Path, story_id: str):
    governance_repo = tmp_path / "governance"
    make_feature_tree(governance_repo, "platform", "identity", "auth-login")
    make_feature_tree(governance_repo, "platform", "identity", "auth-mfa")

    payload, code = run_script([
        "move-stories",
        "--governance-repo",
        str(governance_repo),
        "--source-feature-id",
        "auth-login",
        "--source-domain",
        "platform",
        "--source-service",
        "identity",
        "--target-feature-id",
        "auth-mfa",
        "--target-domain",
        "platform",
        "--target-service",
        "identity",
        "--story-ids",
        story_id,
    ])

    assert code == 1
    assert payload["error"] == "invalid_story_id"
    assert payload["total_moved"] == 0


def test_move_stories_preflight_fails_on_destination_conflict(tmp_path: Path):
    governance_repo = tmp_path / "governance"
    source_dir = make_feature_tree(governance_repo, "platform", "identity", "auth-login")
    target_dir = make_feature_tree(governance_repo, "platform", "identity", "auth-mfa")
    make_story_file(source_dir / "stories", "story-1", "pending")
    # Pre-create the destination so there is a conflict
    make_story_file(target_dir / "stories", "story-1", "pending")

    payload, code = run_script([
        "move-stories",
        "--governance-repo",
        str(governance_repo),
        "--source-feature-id",
        "auth-login",
        "--source-domain",
        "platform",
        "--source-service",
        "identity",
        "--target-feature-id",
        "auth-mfa",
        "--target-domain",
        "platform",
        "--target-service",
        "identity",
        "--story-ids",
        "story-1",
    ])

    assert code == 1
    assert payload["error"] == "destination_conflict"
    assert payload["total_moved"] == 0
    # Source file must remain untouched
    assert (source_dir / "stories" / "story-1.md").exists()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([str(TEST_FILE)]))