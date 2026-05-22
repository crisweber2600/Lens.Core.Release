#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest==9.0.3", "pyyaml==6.0.3"]
# ///
"""Validate the imported plain NextLens command surface."""

from __future__ import annotations

from pathlib import Path


TEST_FILE = Path(__file__).resolve()
MODULE_ROOT = TEST_FILE.parents[2]
REPO_ROOT = MODULE_ROOT.parents[1]

RAW_SKILLS_ROOT = REPO_ROOT / "skills"
WORK_SKILLS_ROOT = MODULE_ROOT / "skills"
MODULE_PROMPTS = MODULE_ROOT / "prompts"
PUBLIC_PROMPTS = REPO_ROOT / ".github" / "prompts"

EXPECTED_RAW_SKILLS = {
    "lens-businessplan",
    "lens-constitution",
    "lens-dev",
    "lens-doctor",
    "lens-expressplan",
    "lens-finalizeplan",
    "lens-ledger-promotion",
    "lens-lifecycle",
    "lens-map-audit",
    "lens-next",
    "lens-nextlens-bugfix",
    "lens-preflight",
    "lens-preplan",
    "lens-projection-rebuild",
    "lens-reporting-snapshot",
    "lens-salmon-impact",
    "lens-setup",
    "lens-techplan",
    "lens-topology-design",
    "lens-work-intake",
}

PUBLIC_NEXTLENS_COMMANDS = {
    "lens-doctor",
    "lens-ledger-promotion",
    "lens-lifecycle",
    "lens-map-audit",
    "lens-projection-rebuild",
    "lens-reporting-snapshot",
    "lens-salmon-impact",
    "lens-setup",
    "lens-topology-design",
    "lens-work-intake",
}

LEGACY_COMMAND_PREFIXES = ("ausx-", "lens-auspex-",)


def _skill_dirs(root: Path) -> set[str]:
    return {path.name for path in root.glob("lens-*") if path.is_dir()}


def test_raw_nextlens_skill_mirror_is_complete():
    assert _skill_dirs(RAW_SKILLS_ROOT) == EXPECTED_RAW_SKILLS

    for skill in EXPECTED_RAW_SKILLS:
        assert (RAW_SKILLS_ROOT / skill / "SKILL.md").is_file()


def test_plain_nextlens_commands_are_installed_in_lens_work_surface():
    for command in PUBLIC_NEXTLENS_COMMANDS:
        assert (WORK_SKILLS_ROOT / command / "SKILL.md").is_file()
        assert (MODULE_PROMPTS / f"{command}.prompt.md").is_file()
        assert (PUBLIC_PROMPTS / f"{command}.prompt.md").is_file()


def test_legacy_command_directories_and_prompts_are_absent():
    roots = [REPO_ROOT / ".agents" / "skills", WORK_SKILLS_ROOT, MODULE_PROMPTS, PUBLIC_PROMPTS]

    for root in roots:
        if not root.exists():
            continue

        names = [path.name for path in root.iterdir()]
        for name in names:
            assert not name.startswith(LEGACY_COMMAND_PREFIXES)
