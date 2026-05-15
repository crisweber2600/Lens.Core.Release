#!/usr/bin/env python3
"""Conductor contract tests for the NextLens bugfix skill."""

from __future__ import annotations

from pathlib import Path


TEST_FILE = Path(__file__).resolve()
MODULE_ROOT = TEST_FILE.parents[2]
SKILL_MD = MODULE_ROOT / "skills" / "lens-nextlens-bugfix" / "SKILL.md"


def _skill_text() -> str:
    return SKILL_MD.read_text(encoding="utf-8")


def test_skill_derives_branch_identity_from_stable_bug_slug():
    text = _skill_text()

    assert "bugfix_feature_id = nextlens-bugfix-{bug_slug}" in text
    assert "bugfix_feature_slug = nextlens-bugfix-{bug_slug}" in text
    assert "bugfix_working_branch = feature/nextlens-bugfix-{bug_slug}" in text
    assert "feature/nextlens-bugfix-" in text


def test_skill_uses_git_orchestration_branch_prep_and_blocks_reuse():
    text = _skill_text()

    assert "git-orchestration-ops.py prepare-dev-branch" in text
    assert "--repo {allowed_write_root}" in text
    assert "--feature-id {bugfix_feature_id}" in text
    assert "--feature-slug {bugfix_feature_slug}" in text
    assert "--mode feature-id" in text
    assert "dirty_working_tree" in text
    assert "branch_reuse_blocked" in text
    assert "branch_scope_mismatch" in text


def test_skill_completion_gate_blocks_noop_and_missing_commits():
    text = _skill_text()

    assert "starting_head" in text
    assert "git rev-parse --short HEAD" in text
    assert "If they are identical, stop with `bugfix_no_changes`." in text
    assert "If the implementation delegate returns without a target commit, stop with `bugfix_no_changes`." in text
    assert "No-op completion is forbidden." in text


def test_skill_blocks_out_of_scope_target_edits():
    text = _skill_text()

    assert "allowed_write_root" in text
    assert "TargetProjects/nextlens/src/NextLens" in text
    assert "target_boundary_violation" in text
    assert "Validate every changed path stays under `{allowed_write_root}`." in text


def test_skill_keeps_push_pr_and_bug_closeout_with_conductor():
    text = _skill_text()

    assert "do not push, create a PR, close the bug, or report final success" in text
    assert "Those actions belong to the conductor completion gate." in text


def test_skill_completion_gate_pushes_branch_and_records_pr():
    text = _skill_text()

    for required in (
        "git-orchestration-ops.py push",
        "create-pr",
        "gh pr create",
        "PR URL",
        "pr_url",
        "record-quickdev-pr",
        "--namespace nextlens",
        "bugs/nextlens/Fixed/",
    ):
        assert required in text, f"Completion gate missing required PR/closeout detail: {required}"


def test_skill_completion_gate_requires_doctor_evidence_or_rationale():
    text = _skill_text()

    assert "Reference NextLens Doctor output when it applies." in text
    assert "--doctor-status passed" in text
    assert "--doctor-evidence" in text
    assert "--doctor-rationale" in text
    assert "If Doctor validation evidence or an allowed not-applicable/deferred rationale is missing, stop and do not move the artifact." in text


def test_skill_high_blocking_salmon_requires_approved_route_evidence():
    text = _skill_text()

    assert "High or blocking Salmon-linked bugs require approved-route evidence" in text
