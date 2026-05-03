#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest>=8.0", "pyyaml>=6.0"]
# ///
"""Tests for branch-prep.py (E4-S3)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add scripts root to path
TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = TESTS_DIR.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from branch_prep import resolve_branch_name, prepare_branch, VALID_STRATEGIES  # type: ignore


# ---------------------------------------------------------------------------
# resolve_branch_name tests
# ---------------------------------------------------------------------------


def test_flat_strategy_returns_base_branch():
    """Flat strategy returns the base branch unchanged."""
    assert resolve_branch_name("flat", "lens-dev-new-codebase-dogfood", "develop") == "develop"


def test_feature_stub_strategy():
    """feature-stub strategy returns feature/{last-segment-of-feature-id}."""
    result = resolve_branch_name("feature-stub", "lens-dev-new-codebase-dogfood", "develop")
    assert result == "feature/dogfood"


def test_feature_user_strategy():
    """feature-user strategy returns feature/{stub}-{username}."""
    result = resolve_branch_name("feature-user", "lens-dev-new-codebase-dogfood", "develop", username="alice")
    assert result == "feature/dogfood-alice"


def test_feature_user_requires_username():
    """feature-user strategy raises ValueError when username is empty."""
    with pytest.raises(ValueError, match="username"):
        resolve_branch_name("feature-user", "lens-dev-new-codebase-dogfood", "develop", username="")


def test_unknown_strategy_raises():
    """Unknown strategy raises ValueError."""
    with pytest.raises(ValueError, match="Unknown strategy"):
        resolve_branch_name("unknown", "lens-dev-new-codebase-dogfood", "develop")


def test_valid_strategies_tuple():
    """VALID_STRATEGIES contains all three expected values."""
    assert set(VALID_STRATEGIES) == {"flat", "feature-stub", "feature-user"}


# ---------------------------------------------------------------------------
# prepare_branch idempotency tests (mocked git)
# ---------------------------------------------------------------------------


def _mock_run(cmd, cwd, dry_run=False):
    """Fake _run that always returns success."""
    return MagicMock(returncode=0, stdout="", stderr="")


def _make_fake_current_branch(name: str):
    def _cb(repo):
        return name
    return _cb


@patch("branch_prep._run", side_effect=_mock_run)
@patch("branch_prep.branch_exists_local", return_value=False)
@patch("branch_prep.branch_exists_remote", return_value=False)
@patch("branch_prep.current_branch", return_value="develop")
def test_prepare_flat_strategy(mock_cb, mock_re, mock_le, mock_run, tmp_path):
    """Flat strategy returns flat action without creating a branch."""
    result = prepare_branch(
        target_repo=tmp_path,
        feature_id="lens-dev-new-codebase-dogfood",
        strategy="flat",
        base_branch="develop",
    )
    assert result["branch"] == "develop"
    assert result["action"] == "flat"
    assert result["errors"] == []


@patch("branch_prep._run", side_effect=_mock_run)
@patch("branch_prep.branch_exists_local", return_value=False)
@patch("branch_prep.branch_exists_remote", return_value=False)
@patch("branch_prep.current_branch", return_value="develop")
def test_prepare_creates_new_feature_branch(mock_cb, mock_re, mock_le, mock_run, tmp_path):
    """Creates branch when it does not exist locally or remotely."""
    result = prepare_branch(
        target_repo=tmp_path,
        feature_id="lens-dev-new-codebase-dogfood",
        strategy="feature-stub",
        base_branch="develop",
    )
    assert result["branch"] == "feature/dogfood"
    assert result["action"] == "created"
    assert result["errors"] == []


@patch("branch_prep._run", side_effect=_mock_run)
@patch("branch_prep.branch_exists_local", return_value=True)
@patch("branch_prep.branch_exists_remote", return_value=True)
@patch("branch_prep.current_branch", return_value="feature/dogfood")
def test_prepare_resumes_existing_branch(mock_cb, mock_re, mock_le, mock_run, tmp_path):
    """Resumes without creating when branch already exists locally."""
    result = prepare_branch(
        target_repo=tmp_path,
        feature_id="lens-dev-new-codebase-dogfood",
        strategy="feature-stub",
        base_branch="develop",
    )
    assert result["branch"] == "feature/dogfood"
    assert result["action"] == "resumed"
    assert result["errors"] == []


@patch("branch_prep._run", side_effect=_mock_run)
@patch("branch_prep.branch_exists_local", return_value=True)
@patch("branch_prep.branch_exists_remote", return_value=True)
@patch("branch_prep.current_branch", return_value="feature/dogfood")
def test_idempotent_second_run(mock_cb, mock_re, mock_le, mock_run, tmp_path):
    """Second call on an existing branch produces resumed (not created) action."""
    result1 = prepare_branch(tmp_path, "lens-dev-new-codebase-dogfood", "feature-stub", "develop")
    result2 = prepare_branch(tmp_path, "lens-dev-new-codebase-dogfood", "feature-stub", "develop")
    assert result1["action"] == "resumed"
    assert result2["action"] == "resumed"
