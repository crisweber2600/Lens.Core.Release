"""Static contract tests for interactive planning conductors."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).parent.parent.parent
PAYLOAD_ROOT = ROOT.parents[1]
CONTROL_REPO_ROOT = next(
    parent
    for parent in ROOT.parents
    if (parent / "lens.core").is_dir() and (parent / "setup.py").is_file()
)

PUBLISHING_CONDUCTORS = {
    "skills/bmad-lens-businessplan/SKILL.md": "preplan",
    "skills/bmad-lens-techplan/SKILL.md": "businessplan",
    "skills/bmad-lens-devproposal/SKILL.md": "techplan",
    "skills/bmad-lens-finalizeplan/SKILL.md": "techplan",
    "skills/bmad-lens-sprintplan/SKILL.md": "devproposal",
    "skills/bmad-lens-dev/SKILL.md": "finalizeplan",
}


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_techplan_interactive_handoff_boundary_is_explicit():
    text = _read("skills/bmad-lens-techplan/SKILL.md")

    assert "if TechPlan was auto-delegated from `/next`, skip that run-confirmation prompt" in text
    assert "treat that handoff as consent to begin phase entry" in text
    assert "do not continue with conductor-side architecture questions or authoring" in text
    assert "The native architecture workflow owns the interactive session and document creation" in text


def test_businessplan_interactive_handoff_boundary_is_explicit():
    text = _read("skills/bmad-lens-businessplan/SKILL.md")

    assert "present one workflow selection menu (`prd`, `ux-design`, or `both`)" in text
    assert "if BusinessPlan was auto-delegated from `/next`, skip that run-confirmation prompt" in text
    assert "Do not ask a redundant yes/no prompt just to run BusinessPlan" in text
    assert "run as two separate native sessions; after the first completes, ask before launching the second" in text
    assert "do not continue with conductor-side PRD or UX questioning or authoring" in text


def test_governance_publish_steps_require_cli_copy_boundary():
    for relative_path, phase in PUBLISHING_CONDUCTORS.items():
        text = _read(relative_path)

        assert f"publish-to-governance --phase {phase}" in text
        assert "Do not create governance files or directories directly with tool calls or patches" in text


def test_publish_to_governance_contract_requires_cli_execution():
    skill = _read("skills/bmad-lens-git-orchestration/SKILL.md")
    reference = _read("skills/bmad-lens-git-orchestration/references/publish-to-governance.md")

    expected_cli = "uv run {project-root}/lens.core/_bmad/lens-work/skills/bmad-lens-git-orchestration/scripts/git-orchestration-ops.py publish-to-governance"

    assert expected_cli in skill
    assert expected_cli in reference
    assert "Do not create governance files or directories directly with tool calls or patches" in skill
    assert "Do not create governance files or directories directly with tool calls or patches" in reference


def test_dev_contract_uses_repo_scoped_branch_modes_and_final_review_gate():
    text = _read("skills/bmad-lens-dev/SKILL.md")

    assert "one target repo working branch for the entire dev cycle" in text
    assert "present a repo-scoped branching menu on the first dev workflow run for that repo" in text
    assert "`direct-default` — commit on the target repo default branch with no PR" in text
    assert "`feature-id` — create or reuse `feature/{featureId}` and open a single final PR to the target repo default branch. This is the default." in text
    assert "`feature-id-username` — create or reuse `feature/{featureId}-{username}` and open a single final PR to the target repo default branch." in text
    assert "set-dev-branch-mode" in text
    assert "Every task and subtask implementation must be delegated with `runSubagent`." in text
    assert "before any final PR is created, run a full dev-closeout adversarial review and a required party-mode blind-spot challenge" in text


def test_complete_contract_delegates_documentation_to_wrapped_skill():
    skill = _read("skills/bmad-lens-complete/SKILL.md")
    doc_reference = _read("skills/bmad-lens-complete/references/document-project.md")
    finalize_reference = _read("skills/bmad-lens-complete/references/finalize-feature.md")
    module_help = _read("module-help.csv")

    assert "delegates final project documentation to the wrapped Lens document-project workflow" in skill
    assert "Load `./references/document-project.md` and delegate to `bmad-lens-document-project`" in skill

    assert "Load `../../bmad-lens-document-project/SKILL.md` with the current feature context." in doc_reference
    assert "Successful completion of that wrapped run satisfies the documentation gate for the complete workflow" in doc_reference
    assert "docs/README.md" not in doc_reference
    assert "docs/deployment.md" not in doc_reference

    assert "Project documentation captured via `bmad-lens-document-project`" in finalize_reference
    assert "project documentation captured via" in finalize_reference
    assert "docs/README.md" not in finalize_reference

    assert "Lens,bmad-lens-complete,complete-doc-check,CK,Run wrapped project documentation gate before archival" in module_help
    assert "Lens,bmad-lens-document-project,bmad-document-project,DC,Run BMAD document-project with Lens feature docs scope and governance mirroring" in module_help


def test_git_orchestration_contract_documents_prepare_dev_branch_modes():
    text = _read("skills/bmad-lens-git-orchestration/SKILL.md")

    assert "prepare-dev-branch" in text
    assert "`direct-default`" in text
    assert "`feature-id`" in text
    assert "`feature-id-username`" in text
    assert "feature/{featureId}" in text
    assert "feature/{featureId}-{username}" in text


def test_feature_template_documents_dev_closeout_repo_fields():
    text = _read("skills/bmad-lens-feature-yaml/assets/feature-template.yaml")

    assert "dev_branch_mode" in text
    assert "dev_branch_name" in text
    assert "dev_base_branch" in text
    assert "final_pr_url" in text
    assert "final_review_report" in text
    assert "final_party_mode_report" in text


def test_wrapper_delegation_boundary_is_explicit():
    text = _read("skills/bmad-lens-bmad-skill/SKILL.md")

    assert "Delegate and stop" in text
    assert "does not continue phase-conductor execution" in text
    assert "Do not ask follow-on workflow questions" in text


def test_wrapper_declares_feature_scoped_planning_authority():
    text = _read("skills/bmad-lens-bmad-skill/SKILL.md")

    assert "feature.yaml.docs.path` as the authoritative `planning_artifacts` root" in text
    assert "global `docs/planning-artifacts` fallback is only for no-feature runs" in text
    assert "governance copies must not be authored directly" in text


def test_planning_conductors_validate_staged_docs_before_progression():
    for relative_path in (
        "skills/bmad-lens-preplan/SKILL.md",
        "skills/bmad-lens-businessplan/SKILL.md",
        "skills/bmad-lens-techplan/SKILL.md",
        "skills/bmad-lens-expressplan/SKILL.md",
    ):
        text = _read(relative_path)

        assert "--docs-root <resolved staged docs path>" in text or "--docs-root <resolved staged docs path resolved from `feature.yaml.docs.path`>" in text
        assert "--misplaced-root" not in text


def test_promote_to_release_carries_instruction_payloads():
    workflow = (PAYLOAD_ROOT / ".github/workflows/promote-to-release.yml").read_text(encoding="utf-8")

    assert '      - ".github/instructions/**"' in workflow
    assert 'for src in .github/instructions/*.instructions.md; do' in workflow


def test_next_docs_describe_auto_delegate_behavior():
    next_skill = _read("skills/bmad-lens-next/SKILL.md")
    module_help = _read("module-help.csv")
    getting_started = _read("docs/GETTING-STARTED.md")

    assert "The `/next` handoff counts as user consent to start the delegated phase entry sequence" in next_skill
    assert "Resolve the one unblocked next command for the current feature and auto-delegate into it" in module_help
    assert "Resolve the one unblocked next step and load it immediately" in getting_started
    assert "/next` does not show a menu when the next step is deterministic" in getting_started


def test_init_feature_handoff_surfaces_route_through_next():
    module_help = _read("module-help.csv")
    workbench_help = _read("bmad-lens-work-setup/assets/module-help.csv")
    prompt = _read("prompts/lens-new-feature.prompt.md")
    skill = _read("skills/bmad-lens-init-feature/SKILL.md")
    reference = _read("skills/bmad-lens-init-feature/references/init-feature.md")

    assert "Lens,bmad-lens-init-feature,init-feature,IF,Initialize a new feature with 2-branch topology and governance entries,create,<featureId> [--domain] [--service] --track <track> [--dry-run],anytime,,bmad-lens-next:suggest,false" in module_help
    assert "Lens,bmad-lens-init-feature,Create Feature,IF,\"Initialize a new feature with 2-branch topology and governance entries\",create,<featureId> [--domain] [--service] --track <track> [--dry-run],anytime,,bmad-lens-next:suggest,false" in workbench_help
    assert "report the returned `starting_phase` and recommend `/next` or the returned `recommended_command`" in prompt
    assert "report the lifecycle start phase and the next recommended command returned by the script" in skill
    assert "plus `planning_pr_created`, `starting_phase`, `recommended_command`, and `router_command`" in reference


def test_feature_init_prompt_requires_automatic_governance_git():
    prompt = _read("prompts/lens-new-feature.prompt.md")
    skill = _read("skills/bmad-lens-init-feature/SKILL.md")
    reference = _read("skills/bmad-lens-init-feature/references/init-feature.md")

    assert "--execute-governance-git" in prompt
    assert "Report governance git success" in prompt
    assert "`remaining_git_commands`" in prompt
    assert "Return git commands for the user to execute." not in prompt
    assert "governance_commit_sha" in skill
    assert "control_repo_git_commands" in skill
    assert "governance_commit_sha" in reference
    assert "remaining_git_commands" in reference


def test_container_init_prompts_require_automatic_governance_git():
    domain_prompt = _read("prompts/lens-new-domain.prompt.md")
    service_prompt = _read("prompts/lens-new-service.prompt.md")
    skill = _read("skills/bmad-lens-init-feature/SKILL.md")

    assert "--execute-governance-git" in domain_prompt
    assert "--execute-governance-git" in service_prompt
    assert "Report governance git success" in domain_prompt
    assert "Report governance git success" in service_prompt
    assert "`remaining_git_commands`" in domain_prompt
    assert "`remaining_git_commands`" in service_prompt
    assert "Return the git commands for the user to execute." not in domain_prompt
    assert "Return the git commands for the user to execute." not in service_prompt
    assert "governance_commit_sha" in skill
    assert "remaining_git_commands" in skill


def test_new_project_prompt_sequences_domain_service_feature_and_repo_bootstrap():
    prompt = _read("prompts/lens-new-project.prompt.md")

    assert "do not need to know or sequence the lower-level commands themselves" in prompt
    assert "use the `create-domain` subcommand of `skills/bmad-lens-init-feature/scripts/init-feature-ops.py` with `--execute-governance-git`" in prompt
    assert "use the `create-service` subcommand of `skills/bmad-lens-init-feature/scripts/init-feature-ops.py` with `--execute-governance-git`" in prompt
    assert "Do **not** rely on the feature `create` subcommand to bootstrap a new domain or service" in prompt
    assert "use the `create` subcommand of `skills/bmad-lens-init-feature/scripts/init-feature-ops.py` with `--execute-governance-git`" in prompt
    assert "use `skills/bmad-lens-target-repo/scripts/target-repo-ops.py provision` only after feature init succeeds" in prompt
    assert "Support both repo modes in the same flow: an existing remote via `--remote-url`, or a GitHub owner plus repo name via `--owner`, `--repo-name`, and `--create-remote`" in prompt
    assert "recommend `/next` or the returned `recommended_command`" in prompt