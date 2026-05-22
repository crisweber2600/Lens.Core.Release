#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest>=8.0", "pyyaml>=6.0"]
# ///
"""Integration tests for lens-dev SKILL.md conductor contract (E4-S1)."""

from __future__ import annotations

import re
from pathlib import Path

import yaml


TEST_FILE = Path(__file__).resolve()
MODULE_ROOT = TEST_FILE.parents[2]
DEV_SKILL_MD = MODULE_ROOT / "skills" / "lens-dev" / "SKILL.md"


def _skill_text() -> str:
    return DEV_SKILL_MD.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Input / output contract tests
# ---------------------------------------------------------------------------


def test_required_inputs_named():
    """The skill declares all three required inputs."""
    text = _skill_text()
    for field in ("feature_id", "governance_repo", "control_repo"):
        assert field in text, f"Required input '{field}' missing from lens-dev SKILL.md"


def test_output_contract_includes_story_commits():
    """Output contract lists story-level commit references."""
    text = _skill_text()
    assert re.search(r"story.level commit", text, re.IGNORECASE), (
        "Output contract must mention story-level commit references"
    )


def test_output_contract_includes_dev_session_updates():
    """Output contract mentions dev-session state updates."""
    text = _skill_text()
    assert re.search(r"dev.session", text, re.IGNORECASE), (
        "Output contract must mention dev-session state"
    )


# ---------------------------------------------------------------------------
# Error category tests
# ---------------------------------------------------------------------------


def test_hard_stop_errors_documented():
    """Hard-stop error category is explicitly documented."""
    text = _skill_text()
    assert re.search(r"hard.stop", text, re.IGNORECASE), (
        "SKILL.md must document hard-stop error category"
    )


def test_recoverable_errors_documented():
    """Recoverable error category is explicitly documented."""
    text = _skill_text()
    assert re.search(r"recoverable", text, re.IGNORECASE), (
        "SKILL.md must document recoverable error category"
    )


# ---------------------------------------------------------------------------
# Phase entry validation tests
# ---------------------------------------------------------------------------


def test_phase_entry_validates_finalizeplan_complete():
    """Conductor validates feature.yaml phase == finalizeplan-complete at entry."""
    text = _skill_text()
    assert "finalizeplan-complete" in text, (
        "SKILL.md must reference 'finalizeplan-complete' as the required phase gate"
    )


def test_control_feature_docs_branch_activation_precedes_phase_entry_validation():
    """Conductor switches to the topology-correct docs branch before story validation."""
    text = _skill_text()
    activation_index = text.find("## Control Feature Docs Branch Activation")
    validation_index = text.find("## Phase Entry Validation")

    assert activation_index != -1, "SKILL.md must document Control Feature Docs Branch Activation"
    assert validation_index != -1, "SKILL.md must document Phase Entry Validation"
    assert activation_index < validation_index, (
        "Control feature docs branch activation must be documented before phase entry validation"
    )
    assert "{feature_id}-dev" in text
    assert "control repo default branch" in text
    assert "control_docs_branch_checkout_failed" in text
    assert "Do not proceed to `sprint_status_missing`, `story_file_missing`" in text


def test_control_docs_branch_pull_uses_ff_only_syntax():
    """The pull step in branch activation must use `--ff-only origin {branch}` form."""
    text = _skill_text()
    activation_start = text.find("## Control Feature Docs Branch Activation")
    activation_end = text.find("##", activation_start + 1)
    section = text[activation_start:activation_end]
    assert "pull --ff-only origin" in section, (
        "Control branch activation pull step must use "
        "`git pull --ff-only origin {control_docs_branch}` (not `origin/{branch}` ref form)"
    )


def test_sprint_boundary_pause_documented():
    """Sprint boundary pause remains documented for default invocations."""
    text = _skill_text()
    assert re.search(r"sprint.boundary", text, re.IGNORECASE), (
        "SKILL.md must document sprint boundary pause"
    )
    # Must be explicit about requiring user confirmation
    assert re.search(r"user confirmation|explicit.*confirm", text, re.IGNORECASE), (
        "Sprint boundary pause must require explicit user confirmation"
    )


def test_all_stories_invocation_continues_across_sprint_boundaries():
    """Explicit all-stories scope is pre-confirmed to cross sprint boundaries."""
    text = _skill_text()
    assert "continue_across_sprints" in text, (
        "SKILL.md must name the continue_across_sprints session flag"
    )
    assert re.search(r"all stories|all sprints", text, re.IGNORECASE), (
        "SKILL.md must document all-stories/all-sprints invocation behavior"
    )
    # The original/initial invocation pre-confirms sprint-boundary crossings (key concept,
    # not an exact phrase — resilient to minor wording changes in SKILL.md).
    assert re.search(r"invocation.{0,80}confirm", text, re.IGNORECASE | re.DOTALL), (
        "All-stories mode must document that the initial invocation pre-confirms sprint boundary crossings"
    )
    # Continuation is automatic — no interactive numbered menu is shown.
    # Checks for 'immediately' near 'sprint' (within 80 chars), 'without' near 'menu'
    # (within 80 chars), or 'record...boundary...immediately' — all signal the same concept.
    assert re.search(
        r"immediately.{0,80}sprint|without.{0,80}menu|record.{0,80}boundary.{0,80}immediately",
        text, re.IGNORECASE | re.DOTALL,
    ), (
        "All-stories mode must document automatic continuation without an interactive stop"
    )
    # Conductor MUST NOT stop merely because the current sprint completed
    assert re.search(r"must not stop|not stop.{0,80}sprint", text, re.IGNORECASE | re.DOTALL), (
        "All-stories mode must not stop at sprint completion when additional unblocked work remains"
    )


# ---------------------------------------------------------------------------
# Story file section validation tests
# ---------------------------------------------------------------------------


def test_story_file_validation_requires_context():
    """Story file validation checks for a Context section."""
    text = _skill_text()
    assert re.search(r"Context.*section|section.*Context", text, re.IGNORECASE), (
        "SKILL.md must require a 'Context' section in story files"
    )


def test_story_file_validation_requires_acceptance_criteria():
    """Story file validation checks for Acceptance Criteria section."""
    text = _skill_text()
    assert re.search(r"Acceptance Criteria", text, re.IGNORECASE), (
        "SKILL.md must require 'Acceptance Criteria' section in story files"
    )


def test_story_file_validation_requires_implementation_steps():
    """Story file validation checks for Implementation Steps section."""
    text = _skill_text()
    assert re.search(r"Implementation Steps", text, re.IGNORECASE), (
        "SKILL.md must require 'Implementation Steps' section in story files"
    )


def test_story_file_validation_requires_dev_agent_record():
    """Story file validation checks for Dev Agent Record section."""
    text = _skill_text()
    assert re.search(r"Dev Agent Record", text, re.IGNORECASE), (
        "SKILL.md must require 'Dev Agent Record' section in story files"
    )


# ---------------------------------------------------------------------------
# dev-session.yaml schema tests
# ---------------------------------------------------------------------------


def test_dev_session_schema_includes_stories_completed():
    """dev-session.yaml schema includes stories_completed field."""
    text = _skill_text()
    assert "stories_completed" in text, (
        "SKILL.md must document 'stories_completed' in dev-session.yaml schema"
    )


def test_dev_session_schema_includes_last_checkpoint():
    """dev-session.yaml schema includes last_checkpoint field."""
    text = _skill_text()
    assert "last_checkpoint" in text, (
        "SKILL.md must document 'last_checkpoint' in dev-session.yaml schema"
    )


def test_dev_session_schema_includes_status():
    """dev-session.yaml schema includes status field."""
    text = _skill_text()
    assert "status: in-progress" in text or re.search(
        r"status.*in-progress|in-progress.*status", text
    ), (
        "SKILL.md must document 'status' field with 'in-progress' in dev-session.yaml schema"
    )


# ---------------------------------------------------------------------------
# Scope / orchestration-only test
# ---------------------------------------------------------------------------


def test_skill_is_orchestration_only():
    """Skill declares it is orchestration-only and delegates implementation."""
    text = _skill_text()
    assert re.search(r"orchestrat", text, re.IGNORECASE), (
        "SKILL.md must declare orchestration scope"
    )
    assert re.search(r"delegat", text, re.IGNORECASE), (
        "SKILL.md must mention delegation of implementation work"
    )


# ---------------------------------------------------------------------------
# Integration points test
# ---------------------------------------------------------------------------


def test_integration_points_include_git_orchestration():
    """Integration points reference lens-git-orchestration."""
    text = _skill_text()
    assert "lens-git-orchestration" in text, (
        "SKILL.md must list lens-git-orchestration in integration points"
    )


def test_integration_points_include_compat_script():
    """Integration points reference the dev-session compatibility script."""
    text = _skill_text()
    assert "dev-session-compat" in text, (
        "SKILL.md must reference dev-session-compat.py for old-format compatibility"
    )
