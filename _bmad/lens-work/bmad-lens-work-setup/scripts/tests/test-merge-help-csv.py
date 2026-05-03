# /// script
# requires-python = ">=3.9"
# dependencies = ["pytest>=8.0"]
# ///
"""Tests for merge-help-csv.py — anti-zombie CSV merge logic."""

import importlib.util
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "merge-help-csv.py"


def _load_merge_help_csv():
    spec = importlib.util.spec_from_file_location("merge_help_csv", str(SCRIPT))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_mod = _load_merge_help_csv()
merge_help_csv = _mod.merge_help_csv

HEADER = "module,skill,display-name,menu-code,description,action,args,phase,after,before,required,output-location,outputs\n"
LENS_ROW = "Lens,bmad-lens-switch,switch-feature,FE,Switch feature,switch,<featureId>,anytime,,,false,,context paths JSON\n"
OTHER_ROW = "Other,other-skill,other-name,OT,Other skill,run,,anytime,,,false,,output\n"


def write_csv(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def read_csv_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


# ---------------------------------------------------------------------------
# Basic merge behavior
# ---------------------------------------------------------------------------

class TestBasicMerge:
    def test_creates_target_when_missing(self, tmp_path):
        module_csv = tmp_path / "module-help.csv"
        write_csv(module_csv, HEADER + LENS_ROW)
        target_csv = tmp_path / "bmad-help.csv"

        merge_help_csv(module_csv, target_csv)

        assert target_csv.exists()
        lines = read_csv_lines(target_csv)
        assert any("Lens" in l for l in lines)

    def test_appends_to_existing_target(self, tmp_path):
        module_csv = tmp_path / "module-help.csv"
        write_csv(module_csv, HEADER + LENS_ROW)
        target_csv = tmp_path / "bmad-help.csv"
        write_csv(target_csv, HEADER + OTHER_ROW)

        merge_help_csv(module_csv, target_csv)

        lines = read_csv_lines(target_csv)
        assert any("Lens" in l for l in lines)
        assert any("Other" in l for l in lines)

    def test_header_preserved(self, tmp_path):
        module_csv = tmp_path / "module-help.csv"
        write_csv(module_csv, HEADER + LENS_ROW)
        target_csv = tmp_path / "bmad-help.csv"
        write_csv(target_csv, HEADER + OTHER_ROW)

        merge_help_csv(module_csv, target_csv)

        first_line = read_csv_lines(target_csv)[0]
        assert first_line.startswith("module,")


# ---------------------------------------------------------------------------
# Anti-zombie: existing module rows removed before re-add
# ---------------------------------------------------------------------------

class TestAntiZombie:
    def test_removes_existing_module_rows(self, tmp_path):
        module_csv = tmp_path / "module-help.csv"
        write_csv(module_csv, HEADER + LENS_ROW)
        target_csv = tmp_path / "bmad-help.csv"
        old_lens_row = "Lens,bmad-lens-old,old-feature,XX,Old description,old,,anytime,,,false,,old\n"
        write_csv(target_csv, HEADER + old_lens_row + OTHER_ROW)

        merge_help_csv(module_csv, target_csv)

        content = target_csv.read_text(encoding="utf-8")
        # Old row replaced
        assert "bmad-lens-old" not in content
        # New row present
        assert "bmad-lens-switch" in content
        # Other row preserved
        assert "Other" in content

    def test_no_duplicate_lens_entries(self, tmp_path):
        module_csv = tmp_path / "module-help.csv"
        write_csv(module_csv, HEADER + LENS_ROW)
        target_csv = tmp_path / "bmad-help.csv"
        write_csv(target_csv, HEADER + LENS_ROW)

        merge_help_csv(module_csv, target_csv)

        lines = [l for l in read_csv_lines(target_csv) if l.startswith("Lens,")]
        assert len(lines) == 1, "Should have exactly one Lens row after anti-zombie merge"


# ---------------------------------------------------------------------------
# Edge cases: empty/malformed files
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_module_csv_returns_early(self, tmp_path):
        module_csv = tmp_path / "module-help.csv"
        write_csv(module_csv, "")
        target_csv = tmp_path / "bmad-help.csv"
        write_csv(target_csv, HEADER + OTHER_ROW)

        merge_help_csv(module_csv, target_csv)

        # Target should be unchanged (no write occurred)
        content = target_csv.read_text(encoding="utf-8")
        assert "Other" in content

    def test_module_csv_header_only_returns_early(self, tmp_path):
        module_csv = tmp_path / "module-help.csv"
        write_csv(module_csv, HEADER)
        target_csv = tmp_path / "bmad-help.csv"
        write_csv(target_csv, HEADER + OTHER_ROW)

        merge_help_csv(module_csv, target_csv)

        # Target unchanged
        content = target_csv.read_text(encoding="utf-8")
        assert "Other" in content

    def test_empty_target_file_uses_module_header(self, tmp_path):
        module_csv = tmp_path / "module-help.csv"
        write_csv(module_csv, HEADER + LENS_ROW)
        target_csv = tmp_path / "bmad-help.csv"
        write_csv(target_csv, "")  # exists but empty

        merge_help_csv(module_csv, target_csv)

        lines = read_csv_lines(target_csv)
        assert lines[0].startswith("module,")
        assert any("Lens" in l for l in lines)

    def test_module_csv_rows_with_empty_first_row(self, tmp_path):
        """A blank row at the start of data should not cause IndexError."""
        module_csv = tmp_path / "module-help.csv"
        # Empty line followed by a real row
        write_csv(module_csv, HEADER + "\n" + LENS_ROW)
        target_csv = tmp_path / "bmad-help.csv"

        merge_help_csv(module_csv, target_csv)

        assert target_csv.exists()
        content = target_csv.read_text(encoding="utf-8")
        assert "Lens" in content

    def test_target_does_not_exist_creates_new(self, tmp_path):
        module_csv = tmp_path / "module-help.csv"
        write_csv(module_csv, HEADER + LENS_ROW)
        target_csv = tmp_path / "nonexistent-help.csv"

        merge_help_csv(module_csv, target_csv)

        assert target_csv.exists()
