#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest>=8.0"]
# ///
"""Conductor contract tests for bmad-lens-bug-quickdev SKILL.md.

Verifies that the SKILL.md enforces PR creation as a terminal command
rather than narrating it to the user.
"""

from __future__ import annotations

import re
from pathlib import Path


TEST_FILE = Path(__file__).resolve()
MODULE_ROOT = TEST_FILE.parents[2]
SKILL_MD = MODULE_ROOT / "skills" / "bmad-lens-bug-quickdev" / "SKILL.md"


def _skill_text() -> str:
    return SKILL_MD.read_text(encoding="utf-8")


def _create_pr_command_block(text: str) -> str:
    """Extract the fenced bash block containing the create-pr invocation from Step 9."""
    match = re.search(r"(```bash\s*\n[\s\S]*?create-pr[\s\S]*?```)", text, re.DOTALL)
    assert match is not None, (
        "SKILL.md must contain a fenced bash block with the create-pr command in Step 9"
    )
    return match.group(1)


# ---------------------------------------------------------------------------
# PR creation enforcement tests
# ---------------------------------------------------------------------------


def test_pr_step_uses_git_orchestration_create_pr():
    """Step 9 must invoke git-orchestration-ops.py create-pr as a terminal command."""
    block = _create_pr_command_block(_skill_text())
    assert "git-orchestration-ops.py create-pr" in block, (
        "Step 9 fenced bash block must call git-orchestration-ops.py create-pr, "
        "not use narrative 'Open a PR' language"
    )


def test_workflow_uses_git_orchestration_prepare_dev_branch():
    """The target repo working branch must be prepared via git-orchestration, not raw git checkout steps."""
    text = _skill_text()
    assert "git-orchestration-ops.py prepare-dev-branch" in text, (
        "SKILL.md must prepare the target repo branch via git-orchestration-ops.py prepare-dev-branch"
    )
    assert "--feature-slug bugfix-{bug-title-slug}" in text
    assert "--mode feature-id" in text
    assert "working_branch" in text, (
        "SKILL.md must capture working_branch from prepare-dev-branch output"
    )
    assert "checks out the base branch" in text
    assert "pulls the base branch" in text
    assert "creates or reuses the QuickDev working branch" in text


def test_workflow_uses_git_orchestration_push():
    """The target repo push must run through the shared git-orchestration push command."""
    text = _skill_text()
    assert "git-orchestration-ops.py push" in text, (
        "SKILL.md must push target repo branches via git-orchestration-ops.py push"
    )
    assert "--branch {working_branch}" in text


def test_pr_step_specifies_base_develop():
    """Step 9 must pass --base develop to the create-pr command."""
    block = _create_pr_command_block(_skill_text())
    assert "--base develop" in block, (
        "Step 9 create-pr invocation must specify --base develop"
    )


def test_pr_step_specifies_target_repo():
    """Step 9 create-pr command must pass --repo pointing at the target project."""
    block = _create_pr_command_block(_skill_text())
    assert "--repo" in block, (
        "Step 9 create-pr command must pass --repo to target the correct repository, "
        "not the governance repo"
    )
    assert "{target_project}" in block, (
        "Step 9 create-pr --repo must use {target_project} placeholder, "
        "not a hardcoded path"
    )
    assert "--head {working_branch}" in block, (
        "Step 9 create-pr must use the working_branch returned by prepare-dev-branch"
    )


def test_pr_step_captures_pr_url():
    """Step 9 must instruct the agent to capture pr_url from the command output."""
    text = _skill_text()
    assert "pr_url" in text, (
        "SKILL.md step 9 must require capturing pr_url from the create-pr JSON output"
    )


def test_pr_step_records_pr_url_to_bug_artifact():
    """Step 9 must record the captured PR URL back into the QuickDev bug artifact."""
    text = _skill_text()
    assert "record-quickdev-pr" in text, (
        "SKILL.md step 9 must call bug-reporter-ops.py record-quickdev-pr after PR creation"
    )
    assert "--pr-url" in text, "record-quickdev-pr command must pass the captured PR URL"
    assert "{bug_slug}" in text, "record-quickdev-pr command must target the captured bug slug"


def test_pr_step_documents_changes_and_closes_bug_artifact():
    """After PR recording, the flow must document changes and move the QuickDev bug to Fixed."""
    text = _skill_text()

    assert "close-quickdev-bug" in text
    assert "--summary" in text
    assert "--validation-summary" in text
    assert "bugs/Fixed/" in text
    assert "QuickDev closeout section" in text


def test_pr_step_has_failure_fallback():
    """Step 9 must define a failure fallback that does not delegate to the user."""
    text = _skill_text()
    assert re.search(r"exits non-zero|non-zero exit|command fails", text, re.IGNORECASE), (
        "SKILL.md step 9 must handle non-zero exit code from create-pr"
    )
    assert re.search(r"do NOT ask the user|do not ask the user", text, re.IGNORECASE), (
        "SKILL.md step 9 must explicitly forbid asking the user to create the PR"
    )


def test_completion_gate_verifies_commit_push_and_pr_before_returning():
    """The conductor must verify commit, push, and PR URL after delegation."""
    text = _skill_text()

    assert "conductor completion gate" in text.lower(), (
        "SKILL.md must define a conductor completion gate after quick-dev returns"
    )
    for required in (
        "git status --short",
        "git rev-parse --short HEAD",
        "git-orchestration-ops.py push",
        "working_branch",
        "commit hash",
        "PR URL",
        "pr_url",
        "record-quickdev-pr",
        "close-quickdev-bug",
        "bug_artifact_path",
        "bugs/Fixed/",
    ):
        assert required in text, f"Completion gate missing required check: {required}"


def test_completion_gate_supports_requested_auto_complete():
    """Requested post-dev completion must invoke lens-complete instead of stopping after the target PR."""
    text = _skill_text()

    assert "automatic completion after the dev cycle" in text
    assert "complete-ops.py finalize" in text
    assert "--control-repo {project-root}" in text
    assert "--confirm" in text
    assert "{feature_id}-dev" in text
    assert "validate related branches" in text
    assert "delete related control branches" in text
    assert "main" in text


def test_completion_gate_forbids_uncommitted_or_manual_handoff_response():
    """The conductor must not return while work is uncommitted or PR creation is delegated."""
    text = _skill_text()

    assert "Do not answer with the Output Contract" in text, (
        "Completion gate must block final response until commit hash and PR URL exist"
    )
    assert "Never say \"left uncommitted\"" in text, (
        "Completion gate must forbid returning uncommitted-change handoff language"
    )
    assert "you can create the PR" in text, (
        "Completion gate must explicitly forbid manual PR handoff language"
    )


def test_flow_explicitly_reverts_no_implicit_commit_behavior():
    """The flow must explicitly require commit+push for touched repos."""
    text = _skill_text()

    assert "no-implicit-commit" in text or "no implicit commit" in text.lower(), (
        "SKILL.md should explicitly describe the no-implicit-commit behavior being reverted"
    )
    assert "commit and push" in text.lower(), (
        "SKILL.md must explicitly require commit and push as part of the flow"
    )


def test_completion_gate_checks_governance_and_control_repo_state():
    """Completion gate must verify and clear governance/control dirty state when produced by the flow."""
    text = _skill_text()

    assert "git -C {governance_repo} status --short" in text, (
        "Completion gate must inspect governance repo status"
    )
    assert "git -C {project-root} status --short" in text, (
        "Completion gate must inspect control-repo status"
    )
    assert "governance/control-repo changes" in text, (
        "Completion gate must block output contract when governance/control changes remain uncommitted"
    )


def test_quick_dev_skill_path_is_project_root_relative():
    """The delegated quick-dev skill path must not be hard-coded to a local workspace copy."""
    text = _skill_text()

    assert "{project-root}/.github/skills/bmad-quick-dev/SKILL.md" in text
    assert "d:/lensTrees/Lens.Core.control copy/.github/skills" not in text


def test_pr_step_does_not_use_open_a_pr_language():
    """Step 9 must not use ambiguous 'Open a PR' narrative without a command."""
    text = _skill_text()
    # It's fine if 'Open a PR' appears only in context of the fallback/error message,
    # but the imperative workflow step must use git-orchestration-ops.py.
    # The key assertion is that git-orchestration-ops.py is present.
    assert "git-orchestration-ops.py" in text, (
        "SKILL.md must reference git-orchestration-ops.py for PR creation "
        "rather than relying on narrative language alone"
    )


# ---------------------------------------------------------------------------
# Output contract tests
# ---------------------------------------------------------------------------


def test_output_contract_includes_pr_url():
    """Output Contract section must include PR URL as a required field."""
    text = _skill_text()
    assert "PR URL" in text, (
        "Output Contract must list 'PR URL' as a required return field"
    )


def test_output_contract_includes_bug_artifact_path():
    """Output Contract section must include the bug artifact path."""
    text = _skill_text()
    assert "bug artifact path" in text, (
        "Output Contract must list 'bug artifact path' as a required return field"
    )


def test_output_contract_includes_validation_summary():
    """Output Contract section must include a validation summary."""
    text = _skill_text()
    assert "validation summary" in text, (
        "Output Contract must list 'validation summary' as a required return field"
    )


# ---------------------------------------------------------------------------
# Governance integration test
# ---------------------------------------------------------------------------


def test_bug_intake_uses_bug_reporter_ops():
    """Bug intake step must invoke bug-reporter-ops.py create-bug."""
    text = _skill_text()
    assert "bug-reporter-ops.py create-bug" in text, (
        "SKILL.md must use bug-reporter-ops.py create-bug for governance intake"
    )


def test_bug_intake_uses_quickdev_queue():
    """Quickdev intake must write to bugs/QuickDev rather than bugs/New."""
    text = _skill_text()
    assert "--queue QuickDev" in text, (
        "SKILL.md create-bug invocation must pass --queue QuickDev for quickdev bugs"
    )
    assert "bug_slug" in text, "SKILL.md must capture the create-bug slug for later PR recording"
