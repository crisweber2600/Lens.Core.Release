"""Focused regression tests for the FinalizePlan conductor."""

from __future__ import annotations

import csv
import re
from pathlib import Path


REPO_ROOT = Path(__file__).parent.parent.parent.parent.parent.parent
SKILL_PATH = REPO_ROOT / "_bmad/lens-work/skills/lens-finalizeplan/SKILL.md"
MODULE_YAML = REPO_ROOT / "_bmad/lens-work/module.yaml"
MODULE_HELP = REPO_ROOT / "_bmad/lens-work/module-help.csv"
GITHUB_PROMPT = REPO_ROOT / ".github/prompts/lens-finalizeplan.prompt.md"
RELEASE_PROMPT = REPO_ROOT / "_bmad/lens-work/prompts/lens-finalizeplan.prompt.md"


def section_between(content: str, start_marker: str, end_marker: str) -> str:
    start = content.find(start_marker)
    assert start != -1, f"Missing section marker: {start_marker}"
    end = content.find(end_marker, start + len(start_marker))
    assert end != -1, f"Missing section marker after {start_marker}: {end_marker}"
    return content[start:end]


class TestFinalizePlanContract:
    def test_three_step_execution_contract_is_ordered(self):
        content = SKILL_PATH.read_text(encoding="utf-8")
        steps = [
            "review-and-push",
            "plan-pr-readiness",
            "downstream-bundle-and-final-pr",
        ]
        positions = [content.find(step) for step in steps]

        assert all(position != -1 for position in positions), "Missing one or more contract step names"
        assert positions == sorted(positions), "FinalizePlan contract steps are out of order"

    def test_predecessor_gate_accepts_techplan_or_expressplan_complete(self):
        content = SKILL_PATH.read_text(encoding="utf-8")
        activation = section_between(content, "## On Activation", "## Execution Contract")

        assert "techplan-complete" in activation
        assert "expressplan-complete" in activation
        assert "active `techplan`" in activation
        assert "active `expressplan`" in activation

    def test_governance_writes_are_only_through_allowed_boundaries(self):
        content = SKILL_PATH.read_text(encoding="utf-8")

        assert "No direct governance file creation" in content
        assert "publish-to-governance" in content
        assert "lens-git-orchestration" in content
        assert "lens-feature-yaml" in content

        forbidden_patterns = [
            r"create_file.*governance",
            r"write_text.*governance",
            r"mkdir.*governance",
            r"shutil\.copy.*governance",
            r"git add.*governance",
            r"git commit.*governance",
        ]
        for pattern in forbidden_patterns:
            assert not re.search(pattern, content, re.IGNORECASE | re.DOTALL), pattern

    def test_publish_phase_selects_techplan_or_expressplan(self):
        content = SKILL_PATH.read_text(encoding="utf-8")
        step_one = section_between(content, "### Step 1 - review-and-push", "### Step 2")

        assert "upstream publish phase" in step_one.lower()
        assert "--phase techplan" in step_one
        assert "--phase expressplan" in step_one
        assert "--phase {upstream_publish_phase}" in step_one

    def test_step_one_requires_review_acknowledgement_and_pre_review_fixes(self):
        content = SKILL_PATH.read_text(encoding="utf-8")
        step_one = section_between(content, "### Step 1 - review-and-push", "### Step 2")

        assert "finalizeplan-review.md" in step_one
        assert "direct the user to review" in step_one.lower()
        assert "expressplan-adversarial-review.md" in step_one
        assert "Pre-Review Fixes Applied" in step_one
        assert "business-plan.md" in step_one
        assert "tech-plan.md" in step_one
        assert "sprint-plan.md" in step_one

    def test_step_three_delegates_bundle_in_required_order(self):
        content = SKILL_PATH.read_text(encoding="utf-8")
        step_three = section_between(content, "### Step 3 - downstream-bundle-and-final-pr", "## Output Artifacts")
        expected = [
            "lens-bmad-skill --skill bmad-create-epics-and-stories",
            "lens-bmad-skill --skill bmad-check-implementation-readiness",
            "lens-bmad-skill --skill bmad-sprint-planning",
            "lens-bmad-skill --skill bmad-create-story",
        ]
        positions = [step_three.find(item) for item in expected]

        assert all(position != -1 for position in positions), "Missing downstream bundle delegation"
        assert positions == sorted(positions), "Downstream bundle delegations are out of order"
        assert "review-driven planning fixes" in step_three

    def test_finalizeplan_complete_update_happens_only_in_step_three(self):
        content = SKILL_PATH.read_text(encoding="utf-8")
        execution_contract = section_between(content, "## Execution Contract", "## Output Artifacts")
        before_step_three = execution_contract[: execution_contract.find("### Step 3 - downstream-bundle-and-final-pr")]
        step_three = section_between(content, "### Step 3 - downstream-bundle-and-final-pr", "## Output Artifacts")

        assert "finalizeplan-complete" not in before_step_three
        assert "finalizeplan-complete" in step_three


class TestFinalizePlanDiscovery:
    def test_prompt_chain_uses_light_preflight_then_redirects(self):
        github_prompt = GITHUB_PROMPT.read_text(encoding="utf-8")
        release_prompt = RELEASE_PROMPT.read_text(encoding="utf-8")

        assert "light-preflight.py" in github_prompt
        assert "_bmad/lens-work/prompts/lens-finalizeplan.prompt.md" in github_prompt
        assert "lens-finalizeplan/SKILL.md" in release_prompt
        assert "only a redirect" in release_prompt.lower()

    def test_module_yaml_registers_finalizeplan_prompt_once(self):
        content = MODULE_YAML.read_text(encoding="utf-8")

        assert content.count("lens-finalizeplan.prompt.md") == 1

    def test_module_help_has_user_facing_finalizeplan_entry(self):
        with open(MODULE_HELP, encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))

        matches = [row for row in rows if row["skill"] == "lens-finalizeplan"]
        assert len(matches) == 1
        assert matches[0]["display-name"] == "finalizeplan"
        assert matches[0]["phase"] == "phase-4"

    def test_module_help_review_args_include_new_phases(self):
        with open(MODULE_HELP, encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))

        matches = [row for row in rows if row["skill"] == "lens-adversarial-review"]
        assert len(matches) == 1
        assert "finalizeplan" in matches[0]["args"]
        assert "expressplan" in matches[0]["args"]