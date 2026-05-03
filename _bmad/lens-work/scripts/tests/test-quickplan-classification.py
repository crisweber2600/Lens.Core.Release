#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest>=8.0", "pyyaml>=6.0"]
# ///
"""Tests that QuickPlan classification in module.yaml is consistent with SKILL.md and the skill registry."""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml


TEST_FILE = Path(__file__).resolve()
MODULE_ROOT = TEST_FILE.parents[2]
MODULE_YAML = MODULE_ROOT / "module.yaml"
SKILL_REGISTRY = MODULE_ROOT / "assets" / "lens-bmad-skill-registry.json"
QUICKPLAN_SKILL_MD = MODULE_ROOT / "skills" / "bmad-lens-quickplan" / "SKILL.md"

QUICKPLAN_SKILL_ID = "bmad-lens-quickplan"


def _module_data() -> dict:
    return yaml.safe_load(MODULE_YAML.read_text(encoding="utf-8"))


def _registry_data() -> dict:
    return json.loads(SKILL_REGISTRY.read_text(encoding="utf-8"))


def _skill_md_text() -> str:
    return QUICKPLAN_SKILL_MD.read_text(encoding="utf-8")


def test_quickplan_not_in_public_prompts():
    """QuickPlan must not appear in module.yaml public prompts list."""
    data = _module_data()
    prompts = [str(p) for p in data.get("prompts", [])]
    assert QUICKPLAN_SKILL_ID not in prompts, (
        f"{QUICKPLAN_SKILL_ID} must not appear in module.yaml 'prompts' (it is internal)"
    )
    for p in prompts:
        assert "quickplan" not in p.lower(), (
            f"A quickplan entry was found in module.yaml prompts: {p!r}"
        )


def test_quickplan_not_in_public_skills():
    """QuickPlan must not appear in module.yaml public skills list."""
    data = _module_data()
    skills = [str(s) for s in data.get("skills", [])]
    assert QUICKPLAN_SKILL_ID not in skills, (
        f"{QUICKPLAN_SKILL_ID} must not appear in module.yaml 'skills' (it is internal, not public)"
    )
    for s in skills:
        assert "quickplan" not in s.lower(), (
            f"A quickplan entry was found in module.yaml skills: {s!r}"
        )


def test_quickplan_in_internal_skills():
    """QuickPlan must appear in module.yaml internal_skills with classification: internal."""
    data = _module_data()
    internal_skills = data.get("internal_skills", [])
    assert internal_skills, "module.yaml must have an 'internal_skills' section"
    names = [entry.get("name") if isinstance(entry, dict) else str(entry) for entry in internal_skills]
    assert QUICKPLAN_SKILL_ID in names, (
        f"{QUICKPLAN_SKILL_ID} must be listed in module.yaml 'internal_skills'"
    )
    qp_entry = next(
        (e for e in internal_skills if isinstance(e, dict) and e.get("name") == QUICKPLAN_SKILL_ID),
        None,
    )
    assert qp_entry is not None, f"No dict entry for {QUICKPLAN_SKILL_ID} in internal_skills"
    assert qp_entry.get("classification") == "internal", (
        f"module.yaml internal_skills entry for {QUICKPLAN_SKILL_ID} must have classification: internal"
    )


def test_registry_marks_quickplan_as_internal():
    """The skill registry must mark QuickPlan with surface: internal."""
    data = _registry_data()
    skills = data.get("skills", {})
    assert QUICKPLAN_SKILL_ID in skills, (
        f"{QUICKPLAN_SKILL_ID} must be present in lens-bmad-skill-registry.json"
    )
    entry = skills[QUICKPLAN_SKILL_ID]
    assert entry.get("surface") == "internal", (
        f"lens-bmad-skill-registry.json entry for {QUICKPLAN_SKILL_ID} must have surface: internal"
    )


def test_skill_md_declares_internal():
    """SKILL.md must declare QuickPlan as internal-only (no public prompt stub)."""
    text = _skill_md_text()
    # Must say internal-only or internal_only in some form
    assert re.search(r"internal.only|internal only|no public prompt stub", text, re.IGNORECASE), (
        "SKILL.md must declare QuickPlan as internal-only with 'no public prompt stub'"
    )


def test_skill_md_names_invoker():
    """SKILL.md must specify the invoker (bmad-lens-bmad-skill)."""
    text = _skill_md_text()
    assert "bmad-lens-bmad-skill" in text, (
        "SKILL.md must identify 'bmad-lens-bmad-skill' as the invoker for QuickPlan"
    )


def test_classification_is_consistent():
    """Cross-check: module.yaml, skill registry, and SKILL.md all agree on internal classification."""
    module_data = _module_data()
    registry_data = _registry_data()
    skill_text = _skill_md_text()

    # module.yaml: internal_skills contains quickplan with classification=internal
    internal_names = [
        e.get("name") for e in module_data.get("internal_skills", []) if isinstance(e, dict)
    ]
    module_says_internal = QUICKPLAN_SKILL_ID in internal_names

    # registry: surface=internal
    registry_entry = registry_data.get("skills", {}).get(QUICKPLAN_SKILL_ID, {})
    registry_says_internal = registry_entry.get("surface") == "internal"

    # SKILL.md: contains internal-only language
    skill_md_says_internal = bool(
        re.search(r"internal.only|internal only|no public prompt stub", skill_text, re.IGNORECASE)
    )

    assert module_says_internal and registry_says_internal and skill_md_says_internal, (
        f"Classification mismatch: module.yaml={module_says_internal}, "
        f"registry={registry_says_internal}, SKILL.md={skill_md_says_internal}. "
        "All three sources must agree that QuickPlan is internal."
    )
