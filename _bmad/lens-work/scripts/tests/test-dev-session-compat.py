#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest>=8.0", "pyyaml>=6.0"]
# ///
"""Tests for dev-session-compat.py (E4-S2)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

# Add scripts root to path
TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = TESTS_DIR.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from dev_session_compat import detect_format, load, save, translate_to_new  # type: ignore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

OLD_FORMAT_DATA = {
    "epic_number": 5,
    "feature_id": "lens-dev-new-codebase-discover",
    "started_at": "2026-04-30T00:00:00Z",
    "special_instructions": "Execute all stories.",
    "target_repo_name": "lens.core.src.discover",
    "target_repo_path": "TargetProjects/lens-dev/new-codebase/lens.core.src.discover",
    "dev_branch_mode": "feature-id",
    "working_branch": "feature/lens-dev-new-codebase-discover",
    "base_branch": "develop",
    "requires_final_pr": True,
    "total_stories": 8,
    "stories_completed": ["5.4.1", "5.4.2", "5.4.3"],
    "stories_failed": [],
    "current_story_index": 3,
    "final_pr_url": None,
    "status": "in-progress",
}

NEW_FORMAT_DATA = {
    "feature_id": "lens-dev-new-codebase-dogfood",
    "epic_number": "all",
    "working_branch": "feature/dogfood",
    "base_branch": "develop",
    "total_stories": 27,
    "stories_completed": ["E1-S1", "E1-S2", "E3-S5"],
    "stories_failed": [],
    "stories_blocked": [],
    "current_story_index": 16,
    "last_checkpoint": "2026-05-02T00:00:00Z",
    "status": "in-progress",
    "requires_final_pr": True,
    "final_pr_url": None,
}


# ---------------------------------------------------------------------------
# detect_format tests
# ---------------------------------------------------------------------------


def test_detect_old_format_by_dev_branch_mode():
    """Old format detected when dev_branch_mode key is present."""
    assert detect_format(OLD_FORMAT_DATA) == "old"


def test_detect_old_format_by_story_id_pattern():
    """Old format detected when story ids match n.n.n pattern."""
    data = {"stories_completed": ["1.2.3"]}
    assert detect_format(data) == "old"


def test_detect_old_format_by_started_at_without_last_checkpoint():
    """Old format detected when started_at present but last_checkpoint absent."""
    data = {"started_at": "2026-01-01T00:00:00Z"}
    assert detect_format(data) == "old"


def test_detect_new_format():
    """New format detected for current dogfood dev-session data."""
    assert detect_format(NEW_FORMAT_DATA) == "new"


def test_detect_new_format_empty_completed():
    """New format detected when stories_completed is empty."""
    data = {"feature_id": "some-feature", "stories_completed": [], "last_checkpoint": "2026-01-01T00:00:00Z"}
    assert detect_format(data) == "new"


# ---------------------------------------------------------------------------
# translate_to_new tests
# ---------------------------------------------------------------------------


def test_old_format_translates_to_new():
    """Old format is translated to new format dict."""
    result = translate_to_new(OLD_FORMAT_DATA)
    # New-only fields present
    assert "stories_blocked" in result
    assert result["stories_blocked"] == []
    # started_at → last_checkpoint
    assert result["last_checkpoint"] == "2026-04-30T00:00:00Z"
    # Old-only fields removed
    assert "dev_branch_mode" not in result
    assert "special_instructions" not in result
    assert "target_repo_name" not in result
    # Core fields preserved
    assert result["feature_id"] == "lens-dev-new-codebase-discover"
    assert result["working_branch"] == "feature/lens-dev-new-codebase-discover"
    assert result["stories_completed"] == ["5.4.1", "5.4.2", "5.4.3"]
    assert result["requires_final_pr"] is True


def test_old_format_missing_stories_blocked_defaults_to_empty():
    """stories_blocked defaults to [] when not in old format data."""
    result = translate_to_new(OLD_FORMAT_DATA)
    assert result["stories_blocked"] == []


# ---------------------------------------------------------------------------
# load / save roundtrip tests
# ---------------------------------------------------------------------------


def test_load_old_format_returns_new_format(tmp_path):
    """load() on an old-format file returns new-format dict."""
    p = tmp_path / "dev-session.yaml"
    p.write_text(yaml.dump(OLD_FORMAT_DATA, default_flow_style=False), encoding="utf-8")

    loaded = load(p)
    assert "stories_blocked" in loaded
    assert "dev_branch_mode" not in loaded
    assert loaded["last_checkpoint"] == "2026-04-30T00:00:00Z"


def test_load_new_format_returns_passthrough(tmp_path):
    """load() on a new-format file returns it unchanged (passthrough)."""
    p = tmp_path / "dev-session.yaml"
    p.write_text(yaml.dump(NEW_FORMAT_DATA, default_flow_style=False), encoding="utf-8")

    loaded = load(p)
    assert loaded["feature_id"] == "lens-dev-new-codebase-dogfood"
    assert loaded["stories_completed"] == ["E1-S1", "E1-S2", "E3-S5"]
    assert loaded["last_checkpoint"] == "2026-05-02T00:00:00Z"


def test_save_always_writes_new_format(tmp_path):
    """save() writes new-format YAML regardless of what was loaded."""
    p = tmp_path / "dev-session.yaml"
    save(p, dict(NEW_FORMAT_DATA))

    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    # New schema fields present
    assert "stories_blocked" in raw
    assert "last_checkpoint" in raw
    # Old-only fields absent
    assert "dev_branch_mode" not in raw
    assert "special_instructions" not in raw


def test_save_sets_status_when_missing(tmp_path):
    """save() inserts default status when missing."""
    p = tmp_path / "dev-session.yaml"
    data = {"feature_id": "test", "stories_completed": []}
    save(p, data)

    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    assert raw.get("status") == "in-progress"
