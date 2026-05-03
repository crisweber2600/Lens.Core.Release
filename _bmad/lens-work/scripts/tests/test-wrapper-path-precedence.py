#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest>=8.0"]
# ///
"""Focused regressions for wrapper path normalization and precedence rules."""

from __future__ import annotations

from pathlib import Path


TEST_FILE = Path(__file__).resolve()
MODULE_ROOT = TEST_FILE.parents[2]
REPO_ROOT = MODULE_ROOT.parents[1]
GITHUB_PROMPTS = REPO_ROOT / ".github" / "prompts"
BMAD_WRAPPER_SKILL = MODULE_ROOT / "skills" / "lens-bmad-skill" / "SKILL.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_public_wrappers_use_normalized_module_relative_paths():
    """Prompt wrappers must not route through lens.core-prefixed paths."""
    for prompt in sorted(GITHUB_PROMPTS.glob("lens-*.prompt.md")):
        text = _read(prompt)
        assert "lens.core/_bmad/lens-work" not in text, (
            f"{prompt.name} still uses lens.core-prefixed path"
        )


def test_public_wrappers_use_standard_preflight_command():
    expected = "uv run _bmad/lens-work/skills/lens-preflight/scripts/light-preflight.py"
    for prompt in sorted(GITHUB_PROMPTS.glob("lens-*.prompt.md")):
        text = _read(prompt)
        assert expected in text, f"{prompt.name} missing normalized preflight command"


def test_bmad_wrapper_declares_output_path_precedence_and_logging():
    text = _read(BMAD_WRAPPER_SKILL)
    for phrase in [
        "Precedence: caller-supplied --output-path wins first",
        "Then feature.yaml docs.path override",
        "Finally module default fallback",
        "Precedence: caller-supplied --output-path wins first.",
        "Then feature.yaml target repo override",
        "pathlib.Path",
        "Never resolve output paths silently",
        "winning source (`caller`, `feature-yaml`, or `module-default`)",
    ]:
        assert phrase in text, f"Missing precedence/logging contract phrase: {phrase}"
