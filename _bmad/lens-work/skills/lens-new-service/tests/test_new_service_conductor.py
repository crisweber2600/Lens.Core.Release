"""Contract tests for the lens-new-service prompt and conductor skill."""

from __future__ import annotations

from pathlib import Path


TEST_FILE = Path(__file__).resolve()
SKILL_DIR = TEST_FILE.parents[1]
MODULE_ROOT = TEST_FILE.parents[3]
SKILL_MD = SKILL_DIR / "SKILL.md"
RELEASE_PROMPT = MODULE_ROOT / "prompts" / "lens-new-service.prompt.md"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_release_prompt_surfaces_related_service_clone_guidance() -> None:
    text = read_text(RELEASE_PROMPT)
    assert "TargetProjects/{domain}/{service}" in text
    assert "before running `/new-feature`" in text
    assert "related_service_clone_guidance" in text


def test_skill_surfaces_related_service_clone_guidance() -> None:
    text = read_text(SKILL_MD)
    assert "TargetProjects/{domain}/{service}" in text
    assert "before running `/new-feature`" in text
    assert "related_service_clone_guidance" in text