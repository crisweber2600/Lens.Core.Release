#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest>=8.0", "pyyaml>=6.0"]
# ///
"""Regression tests for unique Lens command/prompt registrations."""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

import yaml


TEST_FILE = Path(__file__).resolve()
MODULE_ROOT = TEST_FILE.parents[2]
MODULE_YAML = MODULE_ROOT / "module.yaml"
MODULE_HELP = MODULE_ROOT / "module-help.csv"
SETUP_MODULE_HELP = MODULE_ROOT / "lens-work-setup" / "assets" / "module-help.csv"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _prompt_names() -> list[str]:
    data = yaml.safe_load(_read_text(MODULE_YAML))
    prompts = data.get("prompts", [])
    assert isinstance(prompts, list), "module.yaml prompts must be a list"
    return [str(value) for value in prompts]


def _help_keys(path: Path) -> list[tuple[str, str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    keys: list[tuple[str, str, str]] = []
    for row in rows:
        skill = (row.get("skill") or "").strip()
        display_name = (row.get("display-name") or "").strip().lower()
        action = (row.get("action") or "").strip().lower()
        if skill and display_name and action:
            keys.append((skill, display_name, action))
    return keys


def test_module_yaml_prompt_names_are_unique():
    prompts = _prompt_names()
    counts = Counter(prompts)
    duplicates = sorted(name for name, count in counts.items() if count > 1)
    assert not duplicates, f"Duplicate prompt entries in module.yaml: {duplicates}"


def test_lens_expressplan_registered_exactly_once():
    counts = Counter(_prompt_names())
    assert counts["lens-expressplan.prompt.md"] == 1, (
        "lens-expressplan.prompt.md must appear exactly once in module.yaml"
    )


def test_module_help_rows_are_unique_by_skill_display_action():
    keys = _help_keys(MODULE_HELP)
    counts = Counter(keys)
    duplicates = sorted(key for key, count in counts.items() if count > 1)
    assert not duplicates, f"Duplicate rows in module-help.csv: {duplicates}"


def test_setup_asset_module_help_rows_are_unique_by_skill_display_action():
    keys = _help_keys(SETUP_MODULE_HELP)
    counts = Counter(keys)
    duplicates = sorted(key for key, count in counts.items() if count > 1)
    assert not duplicates, f"Duplicate rows in setup asset module-help.csv: {duplicates}"
