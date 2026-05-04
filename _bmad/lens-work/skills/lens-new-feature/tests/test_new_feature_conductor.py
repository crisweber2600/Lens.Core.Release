"""Contract tests for the lens-new-feature prompt and conductor skill."""

from __future__ import annotations

from pathlib import Path


TEST_FILE = Path(__file__).resolve()
SKILL_DIR = TEST_FILE.parents[1]
MODULE_ROOT = TEST_FILE.parents[3]
SKILL_MD = SKILL_DIR / "SKILL.md"
RELEASE_PROMPT = MODULE_ROOT / "prompts" / "lens-new-feature.prompt.md"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_release_prompt_runs_discover_before_feature_create() -> None:
    text = read_text(RELEASE_PROMPT)
    assert "## Repo Inventory Sync" in text
    assert "skills/lens-discover/SKILL.md" in text
    assert "--headless" in text
    assert "target_projects_path" in text
    assert "feature_base_branch" in text
    assert "PR creation time" in text
    assert text.index("## Repo Inventory Sync") < text.index("## Execution")


def test_skill_runs_discover_without_base_branch_selection() -> None:
    text = read_text(SKILL_MD)
    assert "Automatically run `lens-discover --headless`" in text
    assert "feature_base_branch" in text
    assert "PR base branch" in text
    assert "target_projects_path" in text
    assert text.index("Repo Inventory Sync") < text.index("Delegate to Init-Feature")