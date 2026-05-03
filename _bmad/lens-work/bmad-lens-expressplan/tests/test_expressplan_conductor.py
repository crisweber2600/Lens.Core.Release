"""Focused regression tests for ExpressPlan and internal QuickPlan conductors."""

from __future__ import annotations

import csv
import json
from pathlib import Path


REPO_ROOT = Path(__file__).parent.parent.parent.parent.parent.parent
EXPRESS_SKILL = REPO_ROOT / "_bmad/lens-work/skills/bmad-lens-expressplan/SKILL.md"
QUICKPLAN_SKILL = REPO_ROOT / "_bmad/lens-work/skills/bmad-lens-quickplan/SKILL.md"
WRAPPER_SKILL = REPO_ROOT / "_bmad/lens-work/skills/bmad-lens-bmad-skill/SKILL.md"
WRAPPER_REGISTRY = REPO_ROOT / "_bmad/lens-work/assets/lens-bmad-skill-registry.json"
MODULE_YAML = REPO_ROOT / "_bmad/lens-work/module.yaml"
MODULE_HELP = REPO_ROOT / "_bmad/lens-work/module-help.csv"
GITHUB_PROMPT = REPO_ROOT / ".github/prompts/lens-expressplan.prompt.md"
RELEASE_PROMPT = REPO_ROOT / "_bmad/lens-work/prompts/lens-expressplan.prompt.md"
PUBLIC_QUICKPLAN_PROMPTS = [
    REPO_ROOT / ".github/prompts/lens-quickplan.prompt.md",
    REPO_ROOT / "_bmad/lens-work/prompts/lens-quickplan.prompt.md",
]


def section_between(content: str, start_marker: str, end_marker: str) -> str:
    start = content.find(start_marker)
    assert start != -1, f"Missing section marker: {start_marker}"
    end = content.find(end_marker, start + len(start_marker))
    assert end != -1, f"Missing section marker after {start_marker}: {end_marker}"
    return content[start:end]


class TestExpressPlanContract:
    def test_express_gate_and_constitution_gate_precede_delegation(self):
        content = EXPRESS_SKILL.read_text(encoding="utf-8")
        activation = section_between(content, "## On Activation", "## Execution Contract")

        delegation_index = activation.find("bmad-lens-bmad-skill")
        assert delegation_index == -1, "Activation gates should not delegate before the execution contract"
        assert "Express-only gate before any delegation" in activation
        assert "feature.yaml.track" in activation
        assert "Constitution permission check" in activation
        assert "permitted_tracks" in activation

    def test_step_one_delegates_to_internal_quickplan_through_wrapper(self):
        content = EXPRESS_SKILL.read_text(encoding="utf-8")
        step_one = section_between(content, "### Step 1 - quickplan-via-lens-wrapper", "### Step 2")

        assert "bmad-lens-bmad-skill --skill bmad-lens-quickplan" in step_one

    def test_step_two_invokes_express_review_with_party_mode_required(self):
        content = EXPRESS_SKILL.read_text(encoding="utf-8")
        step_two = section_between(content, "### Step 2 - adversarial-review-party-mode", "### Step 3")

        assert "bmad-lens-adversarial-review --phase expressplan --source phase-complete" in step_two
        assert "mandatory party-mode" in step_two.lower()
        assert "fail" in step_two.lower()

    def test_step_three_sets_expressplan_complete_and_signals_finalizeplan(self):
        content = EXPRESS_SKILL.read_text(encoding="utf-8")
        step_three = section_between(content, "### Step 3 - advance-to-finalizeplan", "## Output Artifacts")

        assert "expressplan-complete" in step_three
        assert "/finalizeplan" in step_three
        assert "bmad-lens-feature-yaml" in step_three


class TestQuickPlanInternalOnly:
    def test_quickplan_declares_internal_only_and_outputs(self):
        content = QUICKPLAN_SKILL.read_text(encoding="utf-8")

        assert "Internal-only skill, no public prompt stub" in content
        assert "called via `bmad-lens-bmad-skill` only" in content
        assert "business plan" in content
        assert "John/PM" in content
        assert "tech plan" in content
        assert "Winston/Architect" in content
        assert "sprint plan" in content
        assert "Bob/SM" in content
        assert "business-plan.md" in content
        assert "tech-plan.md" in content
        assert "sprint-plan.md" in content

    def test_no_public_quickplan_prompt_stub_exists(self):
        for path in PUBLIC_QUICKPLAN_PROMPTS:
            assert not path.exists(), f"QuickPlan must remain internal-only: {path}"

    def test_wrapper_table_registers_quickplan_internal_target(self):
        content = WRAPPER_SKILL.read_text(encoding="utf-8")

        assert "bmad-lens-quickplan" in content
        assert "Internal" in content or "internal" in content

    def test_wrapper_registry_registers_quickplan_internal_target(self):
        data = json.loads(WRAPPER_REGISTRY.read_text(encoding="utf-8"))
        entry = data["skills"]["bmad-lens-quickplan"]

        assert entry["displayName"] == "Lens QuickPlan Internal"
        assert entry["contextMode"] == "feature-required"
        assert entry["outputMode"] == "planning-docs"
        assert entry["phaseHints"] == ["expressplan"]
        assert entry["entryPath"] == "skills/bmad-lens-quickplan/SKILL.md"


class TestExpressPlanDiscovery:
    def test_prompt_chain_uses_light_preflight_then_redirects(self):
        github_prompt = GITHUB_PROMPT.read_text(encoding="utf-8")
        release_prompt = RELEASE_PROMPT.read_text(encoding="utf-8")

        assert "light-preflight.py" in github_prompt
        assert "_bmad/lens-work/prompts/lens-expressplan.prompt.md" in github_prompt
        assert "bmad-lens-expressplan/SKILL.md" in release_prompt
        assert "only a redirect" in release_prompt.lower()

    def test_module_yaml_registers_expressplan_prompt_once(self):
        content = MODULE_YAML.read_text(encoding="utf-8")

        assert content.count("lens-expressplan.prompt.md") == 1

    def test_module_help_has_expressplan_but_no_quickplan_entries(self):
        with open(MODULE_HELP, encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))

        express_rows = [row for row in rows if row["skill"] == "bmad-lens-expressplan"]
        quickplan_rows = [row for row in rows if row["skill"] == "bmad-lens-quickplan"]

        assert len(express_rows) == 1
        assert express_rows[0]["display-name"] == "expressplan"
        assert quickplan_rows == []

        batch_rows = [row for row in rows if row["skill"] == "bmad-lens-batch"]
        assert batch_rows
        assert "quickplan" not in batch_rows[0]["args"]