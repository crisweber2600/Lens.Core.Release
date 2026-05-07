---
name: lens-quickdev
description: Governed QuickDev wrapper for dev-ready Lens features. Assesses context, records versioned evidence, and delegates implementation to bmad-quick-dev.
---

# Lens QuickDev Skill

## Overview

`/lens-quickdev` is a public dev-phase wrapper for small, governed implementation asks inside a Lens feature. It is conductor-only: it resolves Lens context, checks that the feature is ready for development, prepares the quickdev evidence trail, delegates implementation to the existing `bmad-quick-dev` engine, and records the result.

This skill does not implement a second quick-dev engine.

## Input Contract

Required input:
- `ask`: the implementation request to assess, plan, and delegate.

Optional inputs:
- `--feature-id <featureId>`: override the active feature context.
- `--dry-run`: perform context resolution, assessment, planning, and evidence drafting without implementation writes.

## Preconditions

- Prompt-start preflight has completed successfully.
- A Lens feature context is resolvable from `--feature-id` or the active workspace context.
- The feature phase is one of the dev-ready phase values before target-repo assessment begins: `finalizeplan-complete`, `dev-ready`, or `dev`.
- `feature.yaml.target_repos` contains a resolvable target repo entry.
- The resolved target repo is reachable and has no unresolved merge state.

## Feature Resolution Gate

Resolve feature context before creating evidence or inspecting source code.

1. If `--feature-id <featureId>` is present, use that value and ignore the active workspace feature for this run.
2. Otherwise read the active feature context from `.lens/personal/context.yaml` and the governance feature index.
3. Read canonical feature state with the sanctioned helper:

```bash
uv run --script lens.core/_bmad/lens-work/skills/lens-feature-yaml/scripts/feature-yaml-ops.py read \
	--governance-repo {governance_repo} \
	--feature-id {feature_id}
```

4. Treat only `finalizeplan-complete`, `dev-ready`, and `dev` as dev-ready phase values for quickdev execution. Any other phase is `quickdev_phase_gate_failed`.
5. Resolve `docs.path` and `docs.governance_docs_path` from the helper payload before creating any quickdev evidence.
6. Resolve the first `target_repos` entry before target-repo assessment. Supported forms are:
	 - a string alias such as `lens.core.src`, resolved through the Lens governance repo inventory or target-repo mapping;
	 - a structured entry with `local_path`, resolved relative to the workspace root when not absolute.
7. If `target_repos` is missing, empty, ambiguous, or cannot be resolved to one reachable local repo, stop with `quickdev_target_repo_unresolved`. Do not infer a write target from open files, current terminal directory, or prompt text.

## Scope Rules

- Default implementation scope is the resolved target repo source tree.
- Feature-associated control-repo docs may be read as context.
- Broader non-source edits require a scope-creep warning and an explicit operator override before edits proceed.
- Any approved override must be recorded in the versioned quickdev evidence artifact.

## Versioned Evidence Scaffold

Every run creates exactly one quickdev evidence artifact before implementation delegation.

1. Resolve `evidence_dir = {docs.path}/quickdev` after the Feature Resolution Gate succeeds.
2. Build `summaryofrequeststub` from the implementation ask by lowercasing, replacing non-alphanumeric runs with `-`, trimming leading/trailing separators, and keeping the result short enough for a readable filename.
3. Find existing files matching `quickdev-[summaryofrequeststub]-vNNN.md` in `evidence_dir`.
4. Select the next version by incrementing the highest existing `vNNN` suffix, starting at `v001` when no prior artifact exists.
5. Create `quickdev-[summaryofrequeststub]-vNNN.md` and never overwrite an existing evidence file.
   - Canonical naming: within `evidence_dir` use filename `quickdev-[summaryofrequeststub]-vNNN.md`; relative to `{docs.path}` the artifact path is `quickdev/quickdev-[summaryofrequeststub]-vNNN.md`.
6. Before delegating to `bmad-quick-dev`, write the artifact with these sections:
	- `Request`
	- `Context Assessment`
	- `Assumptions`
	- `Scope Decision`
	- `Validation Plan`
	- `Implementation Plan`
	- `Delegation Result`
	- `Commit and Publication Record`
7. The versioned quickdev artifact is the only quickdev evidence file for the run. Do not create `commit.md`, `quickdev-commit.md`, or any separate sidecar commit record.

## Execution Contract

1. Confirm prompt-start preflight succeeded.
2. Resolve feature context through the Feature Resolution Gate, honoring explicit `--feature-id` before active context.
3. Block before target-repo assessment when the feature phase is not a dev-ready phase value or the target repo cannot be resolved.
4. Assess the target codebase and feature-associated control docs for the request.
5. Produce an implementation plan, assumptions, and validation plan for the ask.
6. Create a new versioned evidence artifact at `quickdev/quickdev-[summaryofrequeststub]-vNNN.md` under the feature docs path. Never update or replace a previous run's evidence artifact.
7. Resolve Branch and PR Policy, recording `branch_context` or stopping on unsafe branch state before implementation.
8. Build the Delegation Packet. Delegate implementation through the registered `bmad-quick-dev` skill with Lens context. Do not introduce alternate implementation behavior here.
9. Capture the delegate outcome, including changed files, validation result, commit hash, branch, PR URL, and no-op state when present.
10. Update the existing versioned quickdev artifact in place through Run Result Recording.
11. Apply Validation Failure Handling when validation fails at any stage.
12. Publish the versioned evidence artifact through Governance Publication when governance publication is required.

## Delegation Boundary

The only implementation engine for this wrapper is `bmad-quick-dev`. This skill may prepare context and evidence for that delegate, but source-code changes, tests, and implementation-specific decisions belong to the delegate.

## Delegation Packet

Build one delegation packet after the evidence scaffold is created and before invoking implementation:

```yaml
delegate_skill: bmad-quick-dev
feature_id: {feature_id}
target_repo_path: {resolved_target_repo_path}
docs_path: {docs.path}
governance_docs_path: {docs.governance_docs_path}
quickdev_artifact_path: {quickdev_artifact_path}
ask: {ask}
validation_plan: {validation_plan}
branch_context: {branch_context}
```

Invocation rules:
- Prefer the sanctioned Lens BMAD wrapper route when it can invoke registered implementation skills with Lens context: `lens-bmad-skill --skill bmad-quick-dev`.
- If no script facade is available for that route, load the installed registered skill directly from `{project-root}/.github/skills/bmad-quick-dev/SKILL.md` and pass the same Lens context fields.
- Do not reimplement the quick-dev planning, editing, validation, or review workflow inside `lens-quickdev`.

Capture these delegate result fields for later evidence and branch-policy steps:
- `changed_files`
- `validation_command`
- `validation_status`
- `validation_summary`
- `commit_hash`
- `branch`
- `pr_url`
- `no_op`
- `blocked_reason`

## Branch and PR Policy

Resolve branch policy before invoking the delegate.

1. Inspect the resolved target repo branch and working tree state.
2. Block with `quickdev_branch_state_blocked` before implementation when the repo is dirty, detached, in a merge/rebase/cherry-pick state, or when the current branch is ambiguous for the active quickdev run.
3. If the target repo is already on an active in-progress feature branch for the current Lens feature or quickdev run, use that branch and direct commit behavior. Do not prepare an additional branch or PR.
4. If the target repo is not on an active in-progress feature branch, prepare a working branch through Lens git orchestration:

```bash
uv run --script lens.core/_bmad/lens-work/skills/lens-git-orchestration/scripts/git-orchestration-ops.py prepare-dev-branch \
	--repo {target_repo_path} \
	--governance-repo {governance_repo} \
	--feature-id {feature_id} \
	--feature-slug {feature_slug} \
	--mode feature-id
```

5. When a working branch is used, create or reuse the PR through Lens git orchestration after implementation creates a non-empty commit:

```bash
uv run --script lens.core/_bmad/lens-work/skills/lens-git-orchestration/scripts/git-orchestration-ops.py create-pr \
	--repo {target_repo_path} \
	--governance-repo {governance_repo} \
	--head {working_branch} \
	--base {base_branch} \
	--title {pr_title} \
	--body {pr_body}
```

6. Record `branch_context` before delegation with `branch`, `base_branch`, `direct_commit`, `requires_pr`, `pr_url`, and `branch_policy_reason`. Preserve those fields for the quickdev evidence update.

## Run Result Recording

After delegation, update the existing versioned quickdev artifact in place. Preserve the original `quickdev/quickdev-[summaryofrequeststub]-vNNN.md` filename for the entire run.

1. Record the focused validation command, exit status, and concise output summary in `Delegation Result`.
2. Inspect changed files after delegation.
3. If changed files are present and validation is acceptable for commit, create one conventional commit on the resolved branch and record `commit_hash`, `branch`, `base_branch`, `changed_files`, and `pr_url` when present in `Commit and Publication Record`.
4. If no changed files are present, record `no-op` in `Delegation Result`, explain why no source change was needed, and do not create an empty commit.
5. If a PR is created or reused by Branch and PR Policy, record the PR URL in the same versioned artifact.
6. Do not rename the artifact, create a replacement artifact, or split validation/commit details into another file.

## Validation Failure Handling

Validation failures use explicit recovery paths and never rewrite shared history.

1. Pre-commit validation failure:
	- create no commit;
	- mark the versioned quickdev artifact `blocked`;
	- record the failed validation command, output summary, and operator guidance.
2. Local post-commit validation failure before push or PR:
	- do not push;
	- do not create a PR;
	- record `validation-failed` guidance in the artifact with the local commit hash and recovery instructions.
3. Pushed or PR validation failure:
	- do not rewrite shared history;
	- record fix-forward guidance when the branch can continue;
	- record blocked PR recovery when the PR must remain open but blocked.
4. This failure policy applies only to `lens-quickdev`. The `/lens-core-bugfix` route remains separate and keeps its mandatory fresh branch, commit, push, PR, bug-artifact recording, and closeout behavior.

## Governance Publication

Publish completed quickdev evidence through sanctioned Lens publication tooling.

1. Resolve `governance_docs_path` from `feature.yaml.docs.governance_docs_path`.
2. Map `{docs.path}/quickdev/quickdev-[summaryofrequeststub]-vNNN.md` to `{governance_docs_path}/quickdev/quickdev-[summaryofrequeststub]-vNNN.md`.
3. Publish through the Lens publication helper or `git-orchestration-ops.py publish-to-governance`. Do not hand-copy directly into the governance repo when a helper supports the publication.
4. Preserve the unique `vNNN` suffix for reruns. Never collapse multiple runs into one governance artifact.
5. Verify the published artifact content matches the local versioned artifact before reporting success.
6. Record `publication_status`, `governance_artifact_path`, and publication validation summary in `Commit and Publication Record`.

## Metadata and Handoff Reconciliation

Keep feature metadata and implementation-readiness handoff docs aligned before execution and before final reporting.

1. Read feature metadata through `feature-yaml-ops.py read --governance-repo {governance_repo} --feature-id {feature_id}`.
2. Confirm `target_repos` includes `lens.core.src` or the resolved target repo required by the active feature.
3. If `target_repos` must be corrected, use the sanctioned `feature-yaml` update helper. Do not patch governance `feature.yaml` by hand.
4. Confirm implementation-readiness records the versioned `quickdev/quickdev-[summaryofrequeststub]-vNNN.md` evidence rule and sanctioned Governance Publication path.
5. After metadata or readiness changes, run strict handoff validation before delegating implementation or reporting completion.
6. Record the metadata source, target repo confirmation, readiness validation, and handoff validation result in `Context Assessment` or `Commit and Publication Record`.

## Scope Expansion Guard and Final Audit

Protect the wrapper from silently broadening beyond the approved source and feature-associated documentation scope.

1. Treat source changes in the resolved target repo, the public `lens-quickdev` prompt, the `lens-quickdev` skill, module command metadata, tests, and feature-associated control docs under `feature.yaml.docs.path` as approved scope.
2. Treat non-source changes outside `feature.yaml.docs.path`, command metadata, tests, or the sanctioned governance publication path as broader non-source work.
3. Before broader non-source work proceeds, emit a `quickdev_scope_expansion_warning` that names the proposed paths, why they exceed approved scope, and the approval needed to continue.
4. If the user approves the expansion, record `scope_expansion_override`, approved paths, approving instruction, timestamp, and rationale in the versioned quickdev artifact.
5. If approval is not present, stop before editing broader non-source files and record `quickdev_scope_expansion_blocked`.
6. Before completion, run a final audit readiness check covering command surface registration, dev-ready gate, target repo resolution, versioned evidence, delegation packet, branch policy, validation failure handling, governance publication, metadata reconciliation, scope guard, and `/lens-core-bugfix` compatibility.
7. Record unresolved blockers or `audit_ready: true` in the versioned quickdev artifact and completion summary.

## Output Contract

Return:
- Resolved feature id.
- Resolved target repo path or blocking reason.
- Versioned quickdev artifact path.
- Delegated implementation summary.
- Validation summary.
- Commit hash, branch, and PR URL when implementation changed source.
- No-op result when the delegate determines no source changes are required.

## Error Behavior

Hard stops:
- Preflight did not run or failed.
- Feature context is missing.
- Feature phase is not `finalizeplan-complete`, `dev-ready`, or `dev`.
- `target_repos` is missing or unresolved.
- Target repo has unresolved merge conflicts.
- Target repo branch state is dirty, detached, ambiguous, or unrelated to the active quickdev run.
- The requested work exceeds the approved source/docs scope and no override is approved.

Recoverable outcomes:
- No source changes are needed: record a no-op result in the evidence artifact.
- Validation fails before commit: record the blocked validation result and do not commit.
- Validation fails after a local commit but before push: do not push; record recovery guidance.

## Test Hooks

Validate this contract with focused tests or inspection that assert:
- The public prompt is redirect-only and runs preflight before loading this skill.
- This skill names `bmad-quick-dev` as the only implementation engine.
- Non-dev-ready features block before target-repo assessment.
- Missing `target_repos` blocks without guessing a write target.
- Versioned quickdev evidence paths use `quickdev/quickdev-[summaryofrequeststub]-vNNN.md`.
- Reruns create the next available version and do not overwrite prior artifacts.
- No separate `commit.md` or sidecar commit evidence file is created.
- Delegation packet includes feature id, target repo, docs path, evidence artifact path, and ask.
- The fallback loads `{project-root}/.github/skills/bmad-quick-dev/SKILL.md` directly when no script facade exists.
- Delegate outputs include changed files, validation result, commit, branch, PR URL, no-op, and blocker fields.
- Active in-progress feature branches use direct commit behavior without preparing an extra PR branch.
- Non-active branches use `git-orchestration-ops.py prepare-dev-branch` and `git-orchestration-ops.py create-pr`.
- Dirty, detached, merge, rebase, cherry-pick, and ambiguous branch states block before implementation.
- Branch context records branch, base branch, direct-commit flag, PR requirement, PR URL, and policy reason.
- Focused validation command and result are recorded in the existing versioned artifact.
- Non-empty runs record conventional commit hash, changed files, branch, and PR URL when present.
- No-op runs record `no-op` and do not create empty commits.
- Evidence updates preserve the original versioned filename for the run.
- Pre-commit validation failures create no commit and mark the artifact `blocked`.
- Local post-commit validation failures do not push or create PRs and record `validation-failed` guidance.
- Pushed or PR validation failures do not rewrite shared history and record fix-forward or blocked PR recovery.
- `/lens-core-bugfix` remains separate with mandatory fresh branch, commit, push, PR, bug-artifact recording, and closeout behavior.
- Exact versioned artifacts publish to `feature.yaml.docs.governance_docs_path/quickdev/`.
- Publication uses the sanctioned Lens publication helper instead of direct governance authoring.
- Published reruns preserve unique `vNNN` suffixes.
- Publication status and governance artifact path are recorded in the quickdev artifact.
- Feature metadata is read through `feature-yaml-ops.py read` and confirms `target_repos` contains `lens.core.src` or the resolved target repo.
- Metadata corrections use the sanctioned `feature-yaml` update helper rather than hand-editing governance YAML.
- Implementation-readiness records the versioned quickdev rule and sanctioned governance publication path.
- Strict handoff validation runs after metadata or readiness changes and records the result.
- Broader non-source work triggers `quickdev_scope_expansion_warning` before edits proceed.
- Approved scope overrides record `scope_expansion_override`, approved paths, approving instruction, timestamp, and rationale.
- Unapproved broader non-source work stops with `quickdev_scope_expansion_blocked` before editing files.
- Final audit readiness covers command surface, evidence versioning, governance publication, metadata, scope, and core bugfix compatibility, then records `audit_ready: true` or unresolved blockers.
