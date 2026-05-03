#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest>=8.0", "pyyaml>=6.0"]
# ///
"""Tests for lens-complete SKILL.md retrospective-first discipline (E4-S4)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

TEST_FILE = Path(__file__).resolve()
MODULE_ROOT = TEST_FILE.parents[2]
COMPLETE_SKILL_MD = MODULE_ROOT / "skills" / "lens-complete" / "SKILL.md"


def _skill_text() -> str:
    return COMPLETE_SKILL_MD.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# retrospective is a blocker (not advisory) tests
# ---------------------------------------------------------------------------


def test_retrospective_is_blocking_not_advisory():
    """retrospective.md is a blocking prerequisite — the old 'is advisory' pattern must not apply to it."""
    text = _skill_text()
    # Must not have the old pattern "Missing retrospective.md is advisory" or "retrospective is advisory"
    # Note: "blocking prerequisite (not advisory)" is acceptable — we only reject affirmative advisory language
    advisory_retro = re.search(
        r"retrospective[^\n]*\bis advisory\b|Missing retrospective[^\n]*advisory(?! check)",
        text,
        re.IGNORECASE,
    )
    assert advisory_retro is None, (
        "retrospective.md must NOT be described as advisory in lens-complete SKILL.md"
    )


def test_missing_retrospective_returns_fail():
    """Missing retrospective.md must return status: fail, not warn."""
    text = _skill_text()
    # Must mention fail for missing retrospective
    assert re.search(r"retrospective.*missing|blocker.*retrospective_missing", text, re.IGNORECASE), (
        "SKILL.md must document 'retrospective_missing' blocker for missing retrospective.md"
    )


def test_retrospective_not_approved_returns_fail():
    """Retrospective with non-approved status must return fail with blocker."""
    text = _skill_text()
    assert "retrospective_not_approved" in text, (
        "SKILL.md must document 'retrospective_not_approved' blocker"
    )


def test_retrospective_must_have_approved_status():
    """Skill requires retrospective.md frontmatter status == 'approved'."""
    text = _skill_text()
    assert re.search(r"status.*approved|approved.*status", text, re.IGNORECASE), (
        "SKILL.md must require retrospective.md frontmatter status == 'approved'"
    )


# ---------------------------------------------------------------------------
# Error messages guide user to lens-retrospective
# ---------------------------------------------------------------------------


def test_missing_retrospective_error_directs_to_retrospective_skill():
    """Error message for missing retrospective directs user to lens-retrospective."""
    text = _skill_text()
    assert "lens-retrospective" in text, (
        "Error message must direct user to 'lens-retrospective' skill"
    )


# ---------------------------------------------------------------------------
# Finalize operation requires check-preconditions to pass
# ---------------------------------------------------------------------------


def test_finalize_requires_check_preconditions_pass():
    """Finalize operation requires check-preconditions to pass (not just warn)."""
    text = _skill_text()
    # The finalize section must say fail aborts finalize
    assert re.search(r"fail.*status.*aborts|fail.*aborts.*finalize|fail.*abort", text, re.IGNORECASE), (
        "SKILL.md finalize operation must state that a 'fail' status from check-preconditions aborts finalize"
    )


# ---------------------------------------------------------------------------
# Return shape tests
# ---------------------------------------------------------------------------


def test_retrospective_check_in_check_list():
    """check-preconditions return shape includes a retrospective check entry."""
    text = _skill_text()
    assert re.search(r'"name".*"retrospective"|retrospective.*pass', text, re.IGNORECASE), (
        "check-preconditions return shape must include a retrospective check in the checks list"
    )


# ---------------------------------------------------------------------------
# Document-project is still advisory (not changed)
# ---------------------------------------------------------------------------


def test_document_project_remains_advisory():
    """document-project missing remains advisory (warn, not fail) — unchanged from original."""
    text = _skill_text()
    assert re.search(r"document.project.*advisory|document.project.*warn", text, re.IGNORECASE), (
        "document-project missing should remain advisory (warn) in lens-complete SKILL.md"
    )
