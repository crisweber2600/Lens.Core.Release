#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest>=8.0"]
# ///
"""Contract tests for the lens-new-domain prompt and conductor skill."""

from __future__ import annotations

from pathlib import Path


TEST_FILE = Path(__file__).resolve()
SKILL_DIR = TEST_FILE.parents[1]
MODULE_ROOT = TEST_FILE.parents[3]
REPO_ROOT = TEST_FILE.parents[5]
SKILL_MD = SKILL_DIR / "SKILL.md"
RELEASE_PROMPT = MODULE_ROOT / "prompts" / "lens-new-domain.prompt.md"
GITHUB_PROMPT = REPO_ROOT / ".github" / "prompts" / "lens-new-domain.prompt.md"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_github_prompt_runs_preflight_then_release_prompt() -> None:
    text = read_text(GITHUB_PROMPT)
    preflight = "uv run --script lens.core/_bmad/lens-work/skills/lens-preflight/scripts/light-preflight.py"
    release = "lens.core/_bmad/lens-work/prompts/lens-new-domain.prompt.md"
    assert preflight in text
    assert release in text
    assert text.index(preflight) < text.index(release)


def test_release_prompt_routes_to_new_domain_skill() -> None:
    text = read_text(RELEASE_PROMPT)
    assert "skills/lens-new-domain/SKILL.md" in text
    assert "skills/lens-init-feature/SKILL.md" not in text
    assert "light-preflight.py" in text


def test_release_prompt_forbids_inline_repo_probing() -> None:
    text = read_text(RELEASE_PROMPT)
    assert "Do not search the workspace for alternate config files or script locations." in text
    assert "Do not probe alternate governance repo candidates" in text


def test_skill_md_documents_deterministic_config_resolution() -> None:
    text = read_text(SKILL_MD)
    assert "bmadconfig.yaml" in text
    assert ".lens/governance-setup.yaml" in text
    assert "config_missing" in text
    assert "Do not search the workspace for alternate config files or script locations." in text
    assert "Do not probe alternate governance repo candidates" in text
    assert "create-domain" in text