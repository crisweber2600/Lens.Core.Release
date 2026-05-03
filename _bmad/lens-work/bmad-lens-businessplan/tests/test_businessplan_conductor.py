"""Focused regression tests for the businessplan thin conductor (Story BP-3)."""

from __future__ import annotations

import csv
import re
from pathlib import Path


# Resolve repo root from test file location
# Test file is at: {repo_root}/_bmad/lens-work/skills/bmad-lens-businessplan/tests/test_businessplan_conductor.py
# So we need 6 parents to get to repo root
REPO_ROOT = Path(__file__).parent.parent.parent.parent.parent.parent
SKILL_PATH = REPO_ROOT / "_bmad/lens-work/skills/bmad-lens-businessplan/SKILL.md"
MODULE_HELP = REPO_ROOT / "_bmad/lens-work/module-help.csv"
GITHUB_PROMPT = REPO_ROOT / ".github/prompts/lens-businessplan.prompt.md"
RELEASE_PROMPT = REPO_ROOT / "_bmad/lens-work/prompts/lens-businessplan.prompt.md"
AGENT_FILE = REPO_ROOT / "_bmad/lens-work/agents/lens.agent.md"


def section_between(content: str, start_marker: str, end_marker: str) -> str:
    """Return a markdown section slice with clear failure messages."""
    start = content.find(start_marker)
    assert start != -1, f"Missing section marker: {start_marker}"

    end = content.find(end_marker, start)
    assert end != -1, f"Missing section marker after {start_marker}: {end_marker}"
    return content[start:end]


def subsection_between(content: str, start_marker: str, end_marker: str) -> str:
    """Return a subsection slice with clear failure messages."""
    start = content.find(start_marker)
    assert start != -1, f"Missing subsection marker: {start_marker}"

    end = content.find(end_marker, start + len(start_marker))
    assert end != -1, f"Missing subsection marker after {start_marker}: {end_marker}"
    return content[start:end]


class TestWrapperEquivalence:
    """Test conductor routing and wrapper delegation patterns."""

    def test_batch_pass_1_delegates_to_bmad_lens_batch(self):
        """Batch pass 1 must delegate to bmad-lens-batch with --target businessplan."""
        content = SKILL_PATH.read_text(encoding="utf-8")
        
        # Should delegate to bmad-lens-batch
        assert "bmad-lens-batch" in content, "Missing bmad-lens-batch delegation"
        assert "--target businessplan" in content, "Missing --target businessplan parameter"
        
        # Should write businessplan-batch-input.md
        assert "businessplan-batch-input.md" in content, "Missing batch input file reference"
        
        # Batch pass 1 should stop without publishing or authoring
        activation_section = section_between(content, "## On Activation", "## Artifacts")
        batch_pass_1_section = subsection_between(
            activation_section,
            "**Batch pass 1:**",
            "**Batch pass 2:**",
        )
        
        # After batch pass 1, should stop
        assert "stop" in batch_pass_1_section.lower(), "Batch pass 1 should stop after delegation"
        assert "Do not publish" in batch_pass_1_section or "do not update" in batch_pass_1_section, \
            "Batch pass 1 should not update feature.yaml"

    def test_batch_pass_2_resumes_with_pre_approved_context(self):
        """Batch pass 2 must resume with pre-approved context without interactive menu."""
        content = SKILL_PATH.read_text(encoding="utf-8")
        
        activation_section = section_between(content, "## On Activation", "## Artifacts")
        
        # Should have batch pass 2 logic
        assert "**Batch pass 2:**" in activation_section, "Missing batch pass 2 section"
        
        batch_pass_2 = activation_section[activation_section.find("**Batch pass 2:**"):]
        
        # Should resume with batch_resume_context
        assert "batch_resume_context" in batch_pass_2, "Missing batch resume context check"
        
        # Should treat as pre-approved (skip interactive menu unless ambiguous)
        assert "pre-approved" in batch_pass_2.lower() or "skip interactive menu" in batch_pass_2.lower(), \
            "Batch pass 2 should treat selection as pre-approved"

    def test_review_ready_fast_path_validates_then_reviews(self):
        """Review-ready fast path must invoke validate-phase-artifacts before adversarial review."""
        content = SKILL_PATH.read_text(encoding="utf-8")
        
        # Should run validate-phase-artifacts.py with --contract review-ready
        assert "validate-phase-artifacts.py" in content, "Missing validation script invocation"
        assert "--contract review-ready" in content, "Missing review-ready contract check"
        
        # Should jump to adversarial review on pass
        assert "bmad-lens-adversarial-review" in content, "Missing adversarial review delegation"
        assert "--phase businessplan" in content, "Missing --phase businessplan parameter"
        assert "--source phase-complete" in content, "Missing --source phase-complete parameter"
        
        # Validate the sequence: check returns pass, then skip to review
        activation_section = section_between(content, "## On Activation", "## Artifacts")
        
        # Should have review-ready check step
        assert "**Review-ready check:**" in activation_section, "Missing review-ready check step"
        
        # Should have review-ready fast path step
        assert "**Review-ready fast path:**" in activation_section, "Missing review-ready fast path step"
        
        # Fast path should skip menu on status=pass
        fast_path_idx = activation_section.find("**Review-ready fast path:**")
        if fast_path_idx > 0:
            fast_path_section = activation_section[fast_path_idx:fast_path_idx + 500]
            assert "status=pass" in fast_path_section, "Fast path should check for status=pass"
            assert "skip" in fast_path_section.lower(), "Fast path should skip menu"

    def test_prd_route_uses_bmad_lens_bmad_skill(self):
        """PRD authoring must route through bmad-lens-bmad-skill, not direct skill invocation."""
        content = SKILL_PATH.read_text(encoding="utf-8")
        
        # Should delegate through bmad-lens-bmad-skill
        assert "bmad-lens-bmad-skill" in content, "Missing bmad-lens-bmad-skill wrapper"
        assert "--skill bmad-create-prd" in content, "Missing bmad-create-prd skill parameter"
        
        # Should NOT directly invoke bmad-create-prd
        # Check the delegation section specifically
        delegation_section = section_between(content, "**Delegate authoring:**", "## Artifacts")
        
        # PRD route should use bmad-lens-bmad-skill
        prd_pattern = r"`prd`.*?bmad-lens-bmad-skill.*?bmad-create-prd"
        assert re.search(prd_pattern, delegation_section, re.DOTALL), \
            "PRD route should delegate through bmad-lens-bmad-skill"

    def test_ux_route_uses_bmad_lens_bmad_skill(self):
        """UX authoring must route through bmad-lens-bmad-skill, not direct skill invocation."""
        content = SKILL_PATH.read_text(encoding="utf-8")
        
        # Should delegate through bmad-lens-bmad-skill for UX
        assert "bmad-lens-bmad-skill" in content, "Missing bmad-lens-bmad-skill wrapper"
        assert "--skill bmad-create-ux-design" in content, "Missing bmad-create-ux-design skill parameter"
        
        # Check the delegation section
        delegation_section = section_between(content, "**Delegate authoring:**", "## Artifacts")
        
        # UX route should use bmad-lens-bmad-skill
        ux_pattern = r"`ux-design`.*?bmad-lens-bmad-skill.*?bmad-create-ux-design"
        assert re.search(ux_pattern, delegation_section, re.DOTALL), \
            "UX route should delegate through bmad-lens-bmad-skill"

    def test_next_auto_delegation_skips_redundant_confirmation(self):
        """/next auto-delegation must skip redundant run confirmation prompt."""
        content = SKILL_PATH.read_text(encoding="utf-8")
        
        # Should have auto-delegation handling
        assert "auto-delegat" in content.lower(), "Missing auto-delegation handling"
        
        # Should mention /next
        assert "/next" in content, "Missing /next reference"
        
        # Auto-delegation should skip confirmation
        auto_delegation_pattern = r"auto-delegat.*?(skip|do not ask|no.*prompt|treat.*confirmed)"
        assert re.search(auto_delegation_pattern, content, re.IGNORECASE | re.DOTALL), \
            "Auto-delegation from /next should skip redundant confirmation"
        
        # Should still have direct invocation confirmation logic
        assert "direct invocation" in content.lower() or "directly" in content.lower(), \
            "Should distinguish direct invocation from auto-delegation"


class TestGovernanceAudit:
    """Test governance write discipline and publish-to-governance placement."""

    def test_publish_to_governance_appears_before_authoring(self):
        """publish-to-governance --phase preplan must appear before PRD/UX authoring routes."""
        content = SKILL_PATH.read_text(encoding="utf-8")
        
        # Find publish-to-governance invocation
        publish_pattern = r"publish-to-governance.*?--phase preplan"
        publish_match = re.search(publish_pattern, content)
        assert publish_match, "Missing publish-to-governance --phase preplan invocation"
        
        publish_pos = publish_match.start()
        
        # Find authoring delegation section
        delegate_pattern = r"\*\*Delegate authoring:\*\*"
        delegate_match = re.search(delegate_pattern, content)
        assert delegate_match, "Missing delegate authoring section"
        
        delegate_pos = delegate_match.start()
        
        # Publish must come before delegation
        assert publish_pos < delegate_pos, \
            "publish-to-governance must appear before authoring delegation"

    def test_no_direct_governance_writes_in_skill(self):
        """SKILL.md must not contain direct governance write operations."""
        content = SKILL_PATH.read_text(encoding="utf-8")
        
        # Forbidden patterns for direct governance writes
        forbidden_patterns = [
            (r"create_file.*governance", "create_file targeting governance path"),
            (r"write.*governance.*yaml", "write_text to governance YAML"),
            (r"mkdir.*governance", "mkdir in governance repo"),
            (r"shutil\.copy.*governance", "shutil.copy to governance"),
            (r"git add.*governance", "git add in businessplan flow targeting governance"),
            (r"git commit.*governance", "git commit in businessplan flow targeting governance"),
        ]
        
        # Only publish-to-governance is allowed
        for pattern, description in forbidden_patterns:
            # Exclude the legitimate publish-to-governance invocation
            test_content = re.sub(r"publish-to-governance.*?--phase preplan", "", content, flags=re.DOTALL)
            
            match = re.search(pattern, test_content, re.IGNORECASE)
            assert not match, f"Found forbidden governance write pattern: {description}"

    def test_publish_to_governance_uses_cli_wrapper(self):
        """Governance publish must use git-orchestration-ops.py CLI, not inline code."""
        content = SKILL_PATH.read_text(encoding="utf-8")
        
        # Should invoke git-orchestration-ops.py
        assert "git-orchestration-ops.py" in content, "Missing git-orchestration-ops.py CLI invocation"
        
        # Should use publish-to-governance subcommand
        assert "publish-to-governance" in content, "Missing publish-to-governance subcommand"
        
        # Find the actual command invocation in the "On Activation" section (not the overview)
        # Look for the full command line with uv run
        command_pattern = r"uv run.*git-orchestration-ops\.py\s+publish-to-governance"
        match = re.search(command_pattern, content)
        assert match, "Missing git-orchestration-ops.py publish-to-governance command"
        
        # Extract a section around the command to check parameters
        cmd_start = match.start()
        publish_section = content[cmd_start:cmd_start + 500]
        
        # Should pass required parameters
        assert "--governance-repo" in publish_section, "Missing --governance-repo parameter"
        assert "--control-repo" in publish_section, "Missing --control-repo parameter"
        assert "--feature-id" in publish_section, "Missing --feature-id parameter"
        assert "--phase preplan" in publish_section, "Missing --phase preplan parameter"


class TestDiscoverySurface:
    """Test discovery surface integrity in module-help.csv and agent routing."""

    def test_module_help_has_businessplan_entry(self):
        """module-help.csv must have bmad-lens-businessplan entry with correct metadata."""
        with open(MODULE_HELP, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        # Find businessplan entry
        businessplan_row = None
        for row in rows:
            if row["skill"] == "bmad-lens-businessplan":
                businessplan_row = row
                break
        
        assert businessplan_row is not None, "Missing bmad-lens-businessplan entry in module-help.csv"
        
        # Verify metadata
        menu_code = businessplan_row.get("menu-code", "").strip()
        phase = businessplan_row.get("phase", "").strip()
        assert menu_code == "LB", f"Expected menu-code 'LB', got '{menu_code}'"
        assert phase == "phase-2", f"Expected phase 'phase-2', got '{phase}'"
        
        # Verify outputs
        outputs = businessplan_row.get("outputs", "")
        assert "prd.md" in outputs, "Missing prd.md in outputs"
        assert "ux-design.md" in outputs, "Missing ux-design.md in outputs"

    def test_module_help_businessplan_after_preplan(self):
        """businessplan entry must appear after bmad-lens-preplan:plan in module-help.csv."""
        with open(MODULE_HELP, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        preplan_idx = None
        businessplan_idx = None
        
        for idx, row in enumerate(rows):
            if row["skill"] == "bmad-lens-preplan" and row["action"] == "plan":
                preplan_idx = idx
            if row["skill"] == "bmad-lens-businessplan":
                businessplan_idx = idx
        
        assert preplan_idx is not None, "Missing bmad-lens-preplan:plan entry"
        assert businessplan_idx is not None, "Missing bmad-lens-businessplan entry"
        assert businessplan_idx > preplan_idx, \
            "businessplan entry must appear after preplan:plan"

    def test_module_help_businessplan_before_techplan(self):
        """businessplan entry must appear before bmad-lens-techplan:plan in module-help.csv."""
        with open(MODULE_HELP, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        businessplan_idx = None
        techplan_idx = None
        
        for idx, row in enumerate(rows):
            if row["skill"] == "bmad-lens-businessplan":
                businessplan_idx = idx
            if row["skill"] == "bmad-lens-techplan" and row["action"] == "plan":
                techplan_idx = idx
        
        assert businessplan_idx is not None, "Missing bmad-lens-businessplan entry"
        assert techplan_idx is not None, "Missing bmad-lens-techplan:plan entry"
        assert businessplan_idx < techplan_idx, \
            "businessplan entry must appear before techplan:plan"

    def test_agent_routes_through_help_and_next(self):
        """lens.agent.md must route command discovery through help/next, not inline workflow."""
        content = AGENT_FILE.read_text(encoding="utf-8")
        
        # Should reference help and next
        assert "lens-help" in content.lower() or "bmad-lens-help" in content, \
            "Agent must reference help skill"
        assert "lens-next" in content.lower() or "bmad-lens-next" in content, \
            "Agent must reference next skill"
        
        # Should use module-help.csv for discovery
        assert "module-help.csv" in content, "Agent should reference module-help.csv"
        
        # Should NOT inline the businessplan workflow details.
        workflow_refs = re.findall(r"exec=.*businessplan|delegate.*businessplan", content, re.IGNORECASE)
        assert len(workflow_refs) <= 1, \
            f"Agent should not inline businessplan workflow; found {len(workflow_refs)} active references"


class TestPromptChain:
    """Test prompt chain routing and SKILL.md loading."""

    def test_github_prompt_runs_light_preflight(self):
        """.github/prompts/lens-businessplan.prompt.md must run light-preflight.py first."""
        content = GITHUB_PROMPT.read_text(encoding="utf-8")
        
        # Should invoke light-preflight.py
        assert "light-preflight.py" in content, "Missing light-preflight.py invocation"
        
        # Should have preflight check logic
        assert "uv run" in content or "Run preflight" in content, \
            "Missing preflight execution command"

    def test_github_prompt_continues_to_release_prompt(self):
        """.github/prompts/lens-businessplan.prompt.md must continue to release prompt on success."""
        content = GITHUB_PROMPT.read_text(encoding="utf-8")
        
        # Should reference the release prompt
        assert "_bmad/lens-work/prompts/lens-businessplan.prompt.md" in content, \
            "Missing reference to release prompt"
        
        # Should have conditional continuation logic
        assert "exit" in content.lower() or "continue" in content.lower(), \
            "Missing conditional continuation logic"

    def test_release_prompt_loads_skill(self):
        """_bmad/lens-work/prompts/lens-businessplan.prompt.md must load the SKILL.md file."""
        content = RELEASE_PROMPT.read_text(encoding="utf-8")
        
        # Should load the skill file
        assert "bmad-lens-businessplan/SKILL.md" in content, \
            "Missing SKILL.md reference"
        
        # Should have Load instruction
        assert "Load" in content or "load" in content, \
            "Missing Load instruction"

    def test_release_prompt_delegates_to_skill(self):
        """Release prompt must delegate workflow to SKILL.md, not implement inline logic."""
        content = RELEASE_PROMPT.read_text(encoding="utf-8")
        
        # Should delegate to skill
        assert "delegate" in content.lower() or "follow" in content.lower(), \
            "Prompt should delegate to skill"
        
        # Should NOT contain inline businessplan logic in active instructions
        # (it's OK if these appear in comments or descriptions, but not as executable directives)
        forbidden_inline_patterns = [
            r"\buv\s+run\s+.*?\bpublish-to-governance\b",
            r"\binvoke\s+.*?\bbmad-lens-bmad-skill\b",
            r"\bcall\s+.*?\bbmad-create-prd\b",
            r"\bexecute\s+.*?\bbmad-create-ux-design\b",
        ]
        
        # These command invocations should only appear in SKILL.md, not in the prompt
        for pattern in forbidden_inline_patterns:
            assert not re.search(pattern, content, re.IGNORECASE), \
                f"Release prompt should not contain inline command: {pattern}"
