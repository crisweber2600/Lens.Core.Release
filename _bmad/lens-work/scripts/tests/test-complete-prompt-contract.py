#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest>=8.0"]
# ///
"""Contract tests for the /lens-complete prompt controller."""

from __future__ import annotations

from pathlib import Path


TEST_FILE = Path(__file__).resolve()
MODULE_ROOT = TEST_FILE.parents[2]
COMPLETE_PROMPT = MODULE_ROOT / "prompts" / "lens-complete.prompt.md"


def _prompt_text() -> str:
    return COMPLETE_PROMPT.read_text(encoding="utf-8")


def test_finalize_handoff_requires_control_repo_when_available() -> None:
    """The prompt must tell callers to pass --control-repo for normal control-repo completion."""
    text = _prompt_text()

    assert (
        "For `finalize`, if `{control_repo}` resolves and is not the same path as `{governance_repo}`, "
        "pass `--control-repo {control_repo}`."
    ) in text
    assert "governance-only archival" in text