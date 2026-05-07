#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest>=8.0"]
# ///
"""Contract tests for post-review command handling after adversarial reviews."""

from __future__ import annotations

from pathlib import Path


TEST_FILE = Path(__file__).resolve()
MODULE_ROOT = TEST_FILE.parents[2]
ADVERSARIAL_REVIEW_SKILL = MODULE_ROOT / "skills" / "lens-adversarial-review" / "SKILL.md"
PHASE_SKILLS = [
    MODULE_ROOT / "skills" / "lens-preplan" / "SKILL.md",
    MODULE_ROOT / "skills" / "lens-businessplan" / "SKILL.md",
    MODULE_ROOT / "skills" / "lens-techplan" / "SKILL.md",
    MODULE_ROOT / "skills" / "lens-finalizeplan" / "SKILL.md",
    MODULE_ROOT / "skills" / "lens-expressplan" / "SKILL.md",
]


def _adversarial_review_text() -> str:
    return ADVERSARIAL_REVIEW_SKILL.read_text(encoding="utf-8")


def test_phase_complete_pass_requires_post_review_command_handoff():
    """Passing phase-complete reviews must direct callers into the command after review."""
    text = _adversarial_review_text()

    assert "Post-Review Command Contract" in text
    assert "--source phase-complete" in text
    assert "command after the review" in text
    assert "pass-with-warnings" in text


def test_post_review_pr_commands_must_execute_and_capture_pr_url():
    """PR work after reviews must be executed through Lens git orchestration."""
    text = _adversarial_review_text()

    assert "git-orchestration-ops.py" in text
    assert "merge-plan --strategy pr" in text
    assert "create-pr" in text
    assert "pr_url" in text
    assert "MUST NOT ask the user" in text or "Do not tell the user" in text


def test_fail_verdict_blocks_pr_actions():
    """Fail verdicts must block all lifecycle and PR actions."""
    text = _adversarial_review_text()

    assert "A `fail` verdict is terminal" in text
    assert "open PRs" in text
    assert "update `feature.yaml`" in text


def test_manual_rerun_never_triggers_pr_actions():
    """Manual reruns remain review-only and must not trigger PR creation."""
    text = _adversarial_review_text()

    assert "manual-rerun" in text
    assert "never trigger post-review commands" in text
    assert "PR creation" in text


def test_phase_conductors_reference_post_review_contract_after_review():
    """Every phase conductor that runs a completion review points to the shared contract."""
    for path in PHASE_SKILLS:
        text = path.read_text(encoding="utf-8")
        assert "lens-adversarial-review --phase" in text, path
        assert "Post-Review Command Contract" in text, path
