"""
Tests for bugbash-ops.py — Story 3.1 regression tests.
Covers: status-summary command
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "bugbash-ops.py"


def test_pyyaml_is_importable():
    """FINDING-PD04: pyyaml must be available; script raises ImportError otherwise."""
    import importlib
    assert importlib.util.find_spec("yaml") is not None, (
        "pyyaml is not installed — run via `uv run --script bugbash-ops.py` "
        "or install pyyaml>=6.0 in the active environment"
    )


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
    )


def _create_md(folder: Path, name: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.md").write_text(f"---\nstatus: x\n---\nBody", encoding="utf-8")


class TestStatusSummary:
    def test_all_zeros_when_no_bugs(self, tmp_path):
        governance_repo = tmp_path / "gov"
        governance_repo.mkdir()
        result = _run(["status-summary", "--governance-repo", str(governance_repo)])
        assert result.returncode == 0
        data = json.loads(result.stdout.strip())
        assert data == {"New": 0, "Inprogress": 0, "Fixed": 0, "Total": 0}

    def test_counts_bugs_in_each_folder(self, tmp_path):
        governance_repo = tmp_path / "gov"
        _create_md(governance_repo / "bugs" / "New", "bug-aa")
        _create_md(governance_repo / "bugs" / "New", "bug-bb")
        _create_md(governance_repo / "bugs" / "Inprogress", "bug-cc")
        _create_md(governance_repo / "bugs" / "Fixed", "bug-dd")
        _create_md(governance_repo / "bugs" / "Fixed", "bug-ee")
        _create_md(governance_repo / "bugs" / "Fixed", "bug-ff")
        result = _run(["status-summary", "--governance-repo", str(governance_repo)])
        assert result.returncode == 0
        data = json.loads(result.stdout.strip())
        assert data["New"] == 2
        assert data["Inprogress"] == 1
        assert data["Fixed"] == 3
        assert data["Total"] == 6

    def test_exits_1_when_governance_repo_missing(self):
        with tempfile.TemporaryDirectory() as td:
            missing = Path(td) / "does-not-exist"
        result = _run(["status-summary", "--governance-repo", str(missing)])
        assert result.returncode == 1

    def test_help_exits_0(self):
        result = _run(["--help"])
        assert result.returncode == 0

    def test_total_is_sum_of_all(self, tmp_path):
        governance_repo = tmp_path / "gov"
        _create_md(governance_repo / "bugs" / "New", "n1")
        _create_md(governance_repo / "bugs" / "Inprogress", "i1")
        _create_md(governance_repo / "bugs" / "Inprogress", "i2")
        _create_md(governance_repo / "bugs" / "Fixed", "f1")
        result = _run(["status-summary", "--governance-repo", str(governance_repo)])
        assert result.returncode == 0
        data = json.loads(result.stdout.strip())
        assert data["Total"] == data["New"] + data["Inprogress"] + data["Fixed"]
