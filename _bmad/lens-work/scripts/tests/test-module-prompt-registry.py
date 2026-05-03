#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest>=8.0", "pyyaml>=6.0"]
# ///
"""Regression tests for Lens module prompt registration parity.

Run:
    cd TargetProjects/lens-dev/new-codebase/lens.core.src
    uv run --with pytest --with pyyaml pytest _bmad/lens-work/scripts/tests/test-module-prompt-registry.py -q
"""

from __future__ import annotations

from pathlib import Path

import yaml


TEST_FILE = Path(__file__).resolve()
MODULE_ROOT = TEST_FILE.parents[2]
REPO_ROOT = MODULE_ROOT.parents[1]
MODULE_YAML = MODULE_ROOT / "module.yaml"
PROMPTS_DIR = MODULE_ROOT / "prompts"
PUBLIC_PROMPTS_DIR = REPO_ROOT / ".github" / "prompts"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _module_prompts() -> list[str]:
    data = yaml.safe_load(_read_text(MODULE_YAML))
    prompts = data.get("prompts", [])
    assert isinstance(prompts, list), "module.yaml prompts must be a list"
    return [str(p) for p in prompts]


def test_registered_release_prompts_exist():
    """Defect 7 guard: every module.yaml prompt registration must map to a file."""
    missing = [name for name in _module_prompts() if not (PROMPTS_DIR / name).exists()]
    assert not missing, f"Missing registered release prompt files: {missing}"


def test_defect_7_expected_prompt_stubs_now_exist():
    """Ensure previously missing prompt stubs are present in release and public surfaces."""
    expected = [
        "lens-preflight.prompt.md",
        "lens-dev.prompt.md",
        "lens-constitution.prompt.md",
        "lens-upgrade.prompt.md",
        "lens-complete.prompt.md",
        "lens-new-feature.prompt.md",
    ]
    missing_release = [name for name in expected if not (PROMPTS_DIR / name).exists()]
    missing_public = [name for name in expected if not (PUBLIC_PROMPTS_DIR / name).exists()]
    assert not missing_release, f"Missing expected release prompts: {missing_release}"
    assert not missing_public, f"Missing expected public prompts: {missing_public}"
