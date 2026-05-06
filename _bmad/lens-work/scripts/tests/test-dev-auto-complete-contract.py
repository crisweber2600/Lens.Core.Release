#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest>=8.0"]
# ///
"""Contract tests for lens-dev automatic post-dev completion."""

from __future__ import annotations

from pathlib import Path


TEST_FILE = Path(__file__).resolve()
MODULE_ROOT = TEST_FILE.parents[2]
DEV_SKILL_MD = MODULE_ROOT / "skills" / "lens-dev" / "SKILL.md"


def _dev_skill_text() -> str:
    return DEV_SKILL_MD.read_text(encoding="utf-8")


def test_dev_completion_handoff_runs_lens_complete_finalize() -> None:
    """The dev conductor must run complete-ops after explicit auto-complete requests."""
    text = _dev_skill_text()

    assert "Automatic Complete Handoff" in text
    assert "complete-ops.py finalize" in text
    assert "--governance-repo {governance_repo}" in text
    assert "--feature-id {feature_id}" in text
    assert "--control-repo {control_repo}" in text
    assert "--confirm" in text


def test_dev_completion_handoff_uses_feature_dev_branch() -> None:
    """The automatic handoff must use the feature-specific control dev branch."""
    text = _dev_skill_text()

    assert "{feature_id}-dev" in text
    assert "{feature_id}-plan" in text
    assert "deletes the related control branches" in text
    assert "control_repo_merge_failed" in text
    assert "do not simulate completion" in text
