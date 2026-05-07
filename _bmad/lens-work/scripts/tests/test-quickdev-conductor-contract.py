#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest>=8.0"]
# ///
"""Contract tests for the lens-quickdev public prompt and skill."""

from __future__ import annotations

from pathlib import Path


TEST_FILE = Path(__file__).resolve()
MODULE_ROOT = TEST_FILE.parents[2]
REPO_ROOT = MODULE_ROOT.parents[1]
PUBLIC_PROMPT_MD = REPO_ROOT / ".github" / "prompts" / "lens-quickdev.prompt.md"
MODULE_PROMPT_MD = MODULE_ROOT / "prompts" / "lens-quickdev.prompt.md"
SKILL_MD = MODULE_ROOT / "skills" / "lens-quickdev" / "SKILL.md"
MODULE_YAML = MODULE_ROOT / "module.yaml"
MODULE_HELP_CSV = MODULE_ROOT / "module-help.csv"
CORE_BUGFIX_PROMPT_MD = MODULE_ROOT / "prompts" / "lens-core-bugfix.prompt.md"
CORE_BUGFIX_SKILL_MD = MODULE_ROOT / "skills" / "bmad-lens-core-bugfix" / "SKILL.md"


def _public_prompt_text() -> str:
    return PUBLIC_PROMPT_MD.read_text(encoding="utf-8")


def _module_prompt_text() -> str:
    return MODULE_PROMPT_MD.read_text(encoding="utf-8")


def _skill_text() -> str:
    return SKILL_MD.read_text(encoding="utf-8")


def _module_yaml_text() -> str:
    return MODULE_YAML.read_text(encoding="utf-8")


def _module_help_text() -> str:
    return MODULE_HELP_CSV.read_text(encoding="utf-8")


def _core_bugfix_prompt_text() -> str:
    return CORE_BUGFIX_PROMPT_MD.read_text(encoding="utf-8")


def _core_bugfix_skill_text() -> str:
    return CORE_BUGFIX_SKILL_MD.read_text(encoding="utf-8")


def test_public_prompt_runs_preflight_before_module_prompt_loading():
    """The public prompt must run prompt-start preflight before loading the module prompt."""
    text = _public_prompt_text()

    preflight_index = text.index("light-preflight.py --caller lens-quickdev")
    module_prompt_index = text.index("lens.core/_bmad/lens-work/prompts/lens-quickdev.prompt.md")

    assert preflight_index < module_prompt_index
    assert "If that command exits non-zero, stop" in text
    assert "vscode_askQuestions" in text


def test_public_prompt_remains_redirect_only():
    """The prompt surface must not own wrapper business logic."""
    text = _public_prompt_text()

    assert "bmad-quick-dev" not in text
    assert "target_repos" not in text
    assert "quickdev-[summaryofrequeststub]" not in text


def test_module_prompt_is_redirect_only_and_loads_skill():
    """The module prompt should delegate directly to the quickdev skill."""
    text = _module_prompt_text()

    assert "lens-quickdev/SKILL.md" in text
    assert "This prompt is a routing stub only." in text
    assert "prompt-local implementation logic" in text
    assert "light-preflight.py" not in text
    assert "bmad-quick-dev" not in text
    assert "target_repos" not in text


def test_skill_is_conductor_only_and_delegates_to_bmad_quick_dev():
    """The skill must name bmad-quick-dev as the only implementation engine."""
    text = _skill_text()

    assert "conductor-only" in text
    assert "does not implement a second quick-dev engine" in text
    assert "The only implementation engine for this wrapper is `bmad-quick-dev`" in text
    assert "Delegate implementation through the registered `bmad-quick-dev` skill" in text
    assert "Do not reimplement the quick-dev planning, editing, validation, or review workflow" in text


def test_skill_builds_delegation_packet_with_lens_context():
    """Delegation must pass Lens context and the ask to bmad-quick-dev."""
    text = _skill_text()

    assert "## Delegation Packet" in text
    for required_field in (
        "delegate_skill: bmad-quick-dev",
        "feature_id: {feature_id}",
        "target_repo_path: {resolved_target_repo_path}",
        "docs_path: {docs.path}",
        "governance_docs_path: {docs.governance_docs_path}",
        "quickdev_artifact_path: {quickdev_artifact_path}",
        "ask: {ask}",
    ):
        assert required_field in text


def test_skill_defines_registered_quick_dev_fallback():
    """When no script facade exists, the registered skill must be loaded directly."""
    text = _skill_text()

    assert "lens-bmad-skill --skill bmad-quick-dev" in text
    assert "If no script facade is available" in text
    assert "{project-root}/.github/skills/bmad-quick-dev/SKILL.md" in text
    assert "pass the same Lens context fields" in text


def test_skill_captures_delegate_outputs_for_later_steps():
    """Delegate result fields must be available for evidence and branch policy stories."""
    text = _skill_text()

    for required_field in (
        "changed_files",
        "validation_command",
        "validation_status",
        "validation_summary",
        "commit_hash",
        "branch",
        "pr_url",
        "no_op",
        "blocked_reason",
    ):
        assert f"`{required_field}`" in text


def test_skill_defines_branch_and_pr_policy():
    """Branch policy must distinguish active direct commits from orchestrated PR branches."""
    text = _skill_text()

    assert "## Branch and PR Policy" in text
    assert "active in-progress feature branch" in text
    assert "direct commit behavior" in text
    assert "Do not prepare an additional branch or PR" in text
    assert "git-orchestration-ops.py prepare-dev-branch" in text
    assert "git-orchestration-ops.py create-pr" in text


def test_skill_blocks_unsafe_branch_states_before_implementation():
    """Dirty or ambiguous branch states must stop before implementation."""
    text = _skill_text()

    assert "quickdev_branch_state_blocked" in text
    for state in ("dirty", "detached", "merge/rebase/cherry-pick", "ambiguous"):
        assert state in text
    assert "before implementation" in text


def test_skill_records_branch_context_for_evidence():
    """Branch, base, direct/PR mode, and PR URL must be evidence fields."""
    text = _skill_text()

    for required_field in (
        "branch",
        "base_branch",
        "direct_commit",
        "requires_pr",
        "pr_url",
        "branch_policy_reason",
    ):
        assert f"`{required_field}`" in text


def test_skill_records_validation_commit_and_noop_outcomes():
    """Run results must update the existing artifact with validation, commit, and no-op evidence."""
    text = _skill_text()

    assert "## Run Result Recording" in text
    assert "focused validation command, exit status, and concise output summary" in text
    assert "create one conventional commit" in text
    assert "record `commit_hash`, `branch`, `base_branch`, `changed_files`, and `pr_url`" in text
    assert "record `no-op`" in text
    assert "do not create an empty commit" in text


def test_skill_preserves_existing_versioned_artifact_for_result_updates():
    """Validation and commit details must stay in the same versioned artifact."""
    text = _skill_text()

    assert "update the existing versioned quickdev artifact in place" in text
    assert "Preserve the original `quickdev/quickdev-[summaryofrequeststub]-vNNN.md` filename" in text
    assert "Do not rename the artifact" in text
    assert "split validation/commit details into another file" in text


def test_skill_defines_three_validation_failure_paths():
    """Validation failures must have pre-commit, local post-commit, and pushed/PR paths."""
    text = _skill_text()

    assert "## Validation Failure Handling" in text
    assert "Pre-commit validation failure" in text
    assert "create no commit" in text
    assert "mark the versioned quickdev artifact `blocked`" in text
    assert "Local post-commit validation failure before push or PR" in text
    assert "do not push" in text
    assert "do not create a PR" in text
    assert "record `validation-failed` guidance" in text
    assert "Pushed or PR validation failure" in text
    assert "do not rewrite shared history" in text
    assert "fix-forward guidance" in text
    assert "blocked PR recovery" in text


def test_core_bugfix_route_remains_separate_and_mandatory_commit_flow():
    """The core bugfix route must keep its mandatory fresh branch and PR flow."""
    prompt_text = _core_bugfix_prompt_text()
    skill_text = _core_bugfix_skill_text()

    assert "bmad-lens-core-bugfix/SKILL.md" in prompt_text
    assert "lens-quickdev/SKILL.md" not in prompt_text
    assert "commit and push" in skill_text.lower()
    assert "feature/lens-core-bugfix-" in skill_text
    assert "git-orchestration-ops.py push" in skill_text
    assert "git-orchestration-ops.py create-pr" in skill_text
    assert "record-quickdev-pr" in skill_text
    assert "close-quickdev-bug" in skill_text


def test_skill_defines_governance_publication_path():
    """Quickdev evidence must publish to the feature governance quickdev folder."""
    text = _skill_text()

    assert "## Governance Publication" in text
    assert "feature.yaml.docs.governance_docs_path" in text
    assert "{governance_docs_path}/quickdev/quickdev-[summaryofrequeststub]-vNNN.md" in text
    assert "git-orchestration-ops.py publish-to-governance" in text
    assert "Do not hand-copy directly into the governance repo" in text


def test_skill_records_publication_status_and_preserves_versions():
    """Publication must preserve version suffixes and record status in the same artifact."""
    text = _skill_text()

    assert "Preserve the unique `vNNN` suffix for reruns" in text
    assert "Verify the published artifact content matches the local versioned artifact" in text
    assert "`publication_status`" in text
    assert "`governance_artifact_path`" in text
    assert "Commit and Publication Record" in text


def test_skill_reconciles_metadata_and_handoff_docs():
    """Quickdev must keep target repo metadata and handoff docs aligned."""
    text = _skill_text()

    assert "## Metadata and Handoff Reconciliation" in text
    assert "feature-yaml-ops.py read --governance-repo {governance_repo} --feature-id {feature_id}" in text
    assert "`target_repos` includes `lens.core.src`" in text
    assert "sanctioned `feature-yaml` update helper" in text
    assert "Do not patch governance `feature.yaml` by hand" in text


def test_skill_requires_readiness_and_strict_handoff_validation():
    """Handoff validation must cover readiness docs and metadata changes."""
    text = _skill_text()

    assert "implementation-readiness records the versioned `quickdev/quickdev-[summaryofrequeststub]-vNNN.md`" in text
    assert "sanctioned Governance Publication path" in text
    assert "run strict handoff validation" in text
    assert "readiness validation" in text
    assert "handoff validation result" in text


def test_skill_warns_and_blocks_unapproved_scope_expansion():
    """Broader non-source edits must warn and stop without an approved override."""
    text = _skill_text()

    assert "## Scope Expansion Guard and Final Audit" in text
    assert "source changes in the resolved target repo" in text
    assert "feature-associated control docs under `feature.yaml.docs.path`" in text
    assert "quickdev_scope_expansion_warning" in text
    assert "quickdev_scope_expansion_blocked" in text
    assert "stop before editing broader non-source files" in text


def test_skill_records_scope_override_and_final_audit_readiness():
    """Approved scope expansion and final audit readiness must be durable evidence."""
    text = _skill_text()

    assert "`scope_expansion_override`" in text
    assert "approved paths" in text
    assert "approving instruction" in text
    assert "final audit readiness check" in text
    assert "`/lens-core-bugfix` compatibility" in text
    assert "`audit_ready: true`" in text


def test_skill_blocks_before_target_assessment_without_dev_ready_context():
    """Non-dev-ready or unresolved target context must block before repo assessment."""
    text = _skill_text()

    assert "quickdev_phase_gate_failed" in text
    assert "finalizeplan-complete`, `dev-ready`, or `dev`" in text
    assert "Block before target-repo assessment" in text
    assert "quickdev_target_repo_unresolved" in text
    assert "blocks without guessing a write target" in text


def test_skill_defines_versioned_evidence_artifact():
    """Quickdev evidence must use the versioned artifact path from the plan."""
    text = _skill_text()

    assert "Canonical naming: within `evidence_dir` use filename `quickdev-[summaryofrequeststub]-vNNN.md`" in text
    assert "relative to `{docs.path}` the artifact path is `quickdev/quickdev-[summaryofrequeststub]-vNNN.md`" in text
    assert "quickdev/quickdev-[summaryofrequeststub]-vNNN.md" in text
    assert "Versioned quickdev evidence paths" in text
    assert "evidence_dir = {docs.path}/quickdev" in text
    assert "quickdev-[summaryofrequeststub]-vNNN.md" in text
    assert "matching `quickdev/quickdev-[summaryofrequeststub]-vNNN.md` in `evidence_dir`" not in text
    assert "Create `quickdev/quickdev-[summaryofrequeststub]-vNNN.md` and never overwrite an existing evidence file." not in text
    assert "starting at `v001`" in text


def test_skill_requires_evidence_before_delegation():
    """The artifact must contain planning evidence before implementation delegation."""
    text = _skill_text()

    scaffold_index = text.index("Before delegating to `bmad-quick-dev`")
    delegation_index = text.index("Delegate implementation through the registered `bmad-quick-dev` skill")

    assert scaffold_index < delegation_index
    for required_section in (
        "Request",
        "Context Assessment",
        "Assumptions",
        "Scope Decision",
        "Validation Plan",
        "Implementation Plan",
        "Delegation Result",
        "Commit and Publication Record",
    ):
        assert f"`{required_section}`" in text


def test_skill_forbids_overwrite_and_sidecar_commit_records():
    """Reruns must create the next version without commit.md sidecars."""
    text = _skill_text()

    assert "never overwrite an existing evidence file" in text
    assert "Never update or replace a previous run's evidence artifact" in text
    assert "Do not create `commit.md`, `quickdev-commit.md`, or any separate sidecar" in text


def test_module_yaml_exposes_lens_quickdev_once():
    """The module manifest must expose the public prompt and skill exactly once."""
    text = _module_yaml_text()

    assert text.count("lens-quickdev.prompt.md") == 1
    assert text.count("  - lens-quickdev\n") == 1


def test_module_help_exposes_lens_quickdev_once_with_dev_ready_guidance():
    """Operator help must show lens-quickdev once and name its dev-ready-only scope."""
    text = _module_help_text()
    rows = [line for line in text.splitlines() if ",lens-quickdev," in line]

    assert len(rows) == 1
    assert "dev-ready-only" in rows[0]
    assert "versioned quickdev evidence" in rows[0]


def test_skill_uses_sanctioned_feature_yaml_read_for_context_resolution():
    """Feature resolution must use the sanctioned feature-yaml helper."""
    text = _skill_text()

    assert "--feature-id <featureId>" in text
    assert "ignore the active workspace feature" in text
    assert ".lens/personal/context.yaml" in text
    assert "feature-yaml-ops.py read" in text
    assert "--governance-repo {governance_repo}" in text
    assert "--feature-id {feature_id}" in text


def test_skill_resolves_docs_and_target_repos_before_assessment():
    """Docs paths and target repo must resolve before evidence or source assessment."""
    text = _skill_text()

    assert "Resolve `docs.path` and `docs.governance_docs_path`" in text
    assert "Resolve the first `target_repos` entry before target-repo assessment" in text
    assert "string alias such as `lens.core.src`" in text
    assert "structured entry with `local_path`" in text
    assert "Do not infer a write target from open files" in text
