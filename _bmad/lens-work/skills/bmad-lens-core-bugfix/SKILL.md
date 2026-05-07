---
name: bmad-lens-core-bugfix
description: Core bugfix conductor. Takes one Lens core bug report, records bug intake, then runs implementation in target project with required fresh branch, git, and PR flow.
---

# /lens-core-bugfix

## Overview

`/lens-core-bugfix` is a single-core-bug execution flow for direct implementation.
It captures one bug report, records a governance bug artifact, and then delegates
implementation to quick-dev in the target project.

This skill is a thin conductor. It orchestrates inputs and delegation only.

## Non-Negotiables

- Revert any no-implicit-commit behavior for this flow: if this run writes changes in a touched repo, commit and push them before final response.
- Never leave implementation, governance, or control-repo changes uncommitted as a manual handoff.
- Never tell the user to commit, push, or open the PR themselves when the required automation commands are available.
- The complete target-project workflow is mandatory: checkout/pull base, create the fresh Core Bugfix branch from the base branch for this bug, implement, validate, commit, push, create or reuse the PR for this bug branch, document the changes, and close the Core Bugfix bug artifact.
- A successful `/lens-core-bugfix` run requires all of the following to be non-empty and verified: `working_branch`, `commit hash`, `PR URL`, and `bug_artifact_path` (under `bugs/Fixed/`).
- No-op completion is not allowed for this flow. If implementation produces no staged code changes, stop with a structured blocker (`bugfix_no_changes`) and do not report success.
- Every distinct bug must use its own branch created from the base branch. Do not infer continuation from recent conversation history, the current git branch, a previous Output Contract, or an open PR from another bug.

## Required Inputs

Collect these fields before execution:

- `title`
- `description`
- `repro_steps`
- `expected`
- `actual`

If any field is missing, ask only for missing fields and stop until complete.

## Fresh Branch Rule

- This flow has no implicit continuation mode.
- Create the bug intake artifact before deriving branch identity.
- For every new bug, derive `feature_id = lens-core-bugfix-{bug_slug}` and `feature_slug = lens-core-bugfix-{bug_slug}` from the `slug` returned by `bug-reporter-ops.py create-bug`.
- Because `bug_slug` includes a content hash, distinct bug reports produce distinct branch identities even when their titles are similar.
- Do not reuse the previous `working_branch`, active branch, or PR from the current conversation.
- If the user explicitly asks to continue a named existing bugfix branch or PR, continue only when that branch starts with `feature/lens-core-bugfix-`; otherwise stop with `branch_scope_mismatch`.
- If `prepare-dev-branch` reports `reused: true` for a new bug artifact (`status: created`), stop with `branch_reuse_blocked` unless the reused branch exactly matches `feature/{feature_id}` and is known to belong to the same `bug_slug`.

## On Activation

1. Ensure prompt-start preflight already succeeded.
2. Resolve:
   - `governance_repo = {project-root}/TargetProjects/lens/lens-governance`
   - `target_project = {project-root}/TargetProjects/lens-dev/new-codebase/lens.core.src`
   - `legacy_project = {project-root}/TargetProjects/lens-dev/old-codebase/lens.core.src`
3. Create bug intake artifact:

```bash
uv run --script lens.core/_bmad/lens-work/scripts/bug-reporter-ops.py create-bug \
  --title "{title}" \
  --description "{description}\n\nRepro Steps:\n{repro_steps}\n\nExpected:\n{expected}\n\nActual:\n{actual}" \
  --chat-log "Bug report submitted via /lens-core-bugfix." \
  --governance-repo {governance_repo} \
  --queue QuickDev
```

4. Parse script JSON:
   - `status: created` or `status: duplicate` are both valid; continue.
   - Capture `slug` as `bug_slug` and `path` as `bug_artifact_path` for the PR-recording step and Output Contract.
   - Set `feature_id = lens-core-bugfix-{bug_slug}` and `feature_slug = lens-core-bugfix-{bug_slug}`.
   - On non-zero exit, stop and surface error.
5. Load and run `{project-root}/.github/skills/bmad-quick-dev/SKILL.md`.
6. Use this implementation intent exactly:

"Fix this Lens core bug report in `TargetProjects/lens-dev/new-codebase/lens.core.src`.
Title: {title}
Description: {description}
Repro Steps: {repro_steps}
Expected: {expected}
Actual: {actual}

Required workflow in target project:
1) Prepare the working branch by executing this standard Lens git operation from the workspace root:
    ```bash
    uv run --script lens.core/_bmad/lens-work/skills/lens-git-orchestration/scripts/git-orchestration-ops.py prepare-dev-branch \
       --repo {target_project} \
       --governance-repo {governance_repo} \
       --feature-id {feature_id} \
       --feature-slug {feature_slug} \
       --mode feature-id \
       --base-branch develop
    ```
    Capture `working_branch`, `created`, and `reused` from the JSON output and use `working_branch` for all subsequent target-repo validation, push, and PR steps. If this command exits non-zero, stop and surface the exact error.
   The command is mandatory because it checks out the base branch, pulls the base branch, and creates the fresh Core Bugfix working branch from `develop` for this bug. Do not replace it with narrative instructions or skip it when the target repo already appears to be on a usable branch.
   If `working_branch` does not start with `feature/lens-core-bugfix-`, stop with `branch_scope_mismatch`.
   If `reused` is true for a newly created bug artifact, stop with `branch_reuse_blocked` unless the reused branch exactly matches `feature/{feature_id}` and is known to belong to the same `bug_slug`.
2) Before implementing, identify the primary affected Lens command (`lens-core-bugfix`) and inspect the same command in `TargetProjects/lens-dev/old-codebase/lens.core.src` to understand legacy behavior and identify gaps. Use the same command name and closest matching prompt/skill/script entrypoint when available. If no legacy match exists, record that as a gap.
3) If the legacy comparison reveals large gaps that materially change expected behavior, workflow, or outputs, stop and use `vscode_askQuestions` to confirm user intent before implementing.
4) Implement the fix and run relevant validation.
5) Stage and commit the implementation changes in `{target_project}` with a conventional commit message. Commit is mandatory for this flow; do not leave the bugfix branch with uncommitted implementation changes.
6) Push the working branch by executing this standard Lens git operation from the workspace root:
    ```bash
    uv run --script lens.core/_bmad/lens-work/skills/lens-git-orchestration/scripts/git-orchestration-ops.py push \
       --repo {target_project} \
       --governance-repo {governance_repo} \
       --branch {working_branch}
    ```
    If this command exits non-zero, stop and surface the exact error.
7) Create the PR by executing this standard Lens git operation from the workspace root — you MUST execute this command, not narrate it:
   ```bash
   uv run --script lens.core/_bmad/lens-work/skills/lens-git-orchestration/scripts/git-orchestration-ops.py create-pr \
     --repo {target_project} \
     --governance-repo {governance_repo} \
     --head {working_branch} \
     --base develop \
     --title "fix(lens-core): {title}" \
     --body "{bug_context_with_legacy_gap_notes_and_validation_summary}"
   ```
    Capture `pr_url` from the JSON output field. Immediately record it back to the bug artifact by executing this terminal command from the workspace root:
    ```bash
      uv run --script lens.core/_bmad/lens-work/scripts/bug-reporter-ops.py record-quickdev-pr \
       --governance-repo {governance_repo} \
       --slug {bug_slug} \
       --pr-url "{pr_url}"
    ```
    Capture the returned `path` as `bug_artifact_path`. If this command exits non-zero, stop and surface the exact error.
    Then document the changes and close out the Core Bugfix bug by executing this terminal command from the workspace root:
    ```bash
      uv run --script lens.core/_bmad/lens-work/scripts/bug-reporter-ops.py close-quickdev-bug \
       --governance-repo {governance_repo} \
       --slug {bug_slug} \
       --summary "{concise_change_summary}" \
       --validation-summary "{validation_summary}"
    ```
    Capture the returned `path` as the final `bug_artifact_path`; it must point under `bugs/Fixed/`. If this command exits non-zero, stop and surface the exact error.
    If the create-pr command exits non-zero, surface the exact error and run this fallback from the `{target_project}` directory:
   ```bash
   gh pr create \
     --base develop \
     --head {working_branch} \
     --title "fix(lens-core): {title}" \
     --body "{bug_context_with_legacy_gap_notes_and_validation_summary}"
   ```
    Capture the PR URL from the `gh pr create` output, then execute the same `record-quickdev-pr` and `close-quickdev-bug` commands above with the captured PR URL. Do NOT ask the user to create the PR themselves."

8) After quick-dev delegation returns, run this conductor completion gate before responding to the user. This gate is mandatory even if the delegate claims the work is complete:
   - Verify `working_branch` is non-empty and the target project is currently on `{working_branch}`.
   - Verify `working_branch` starts with `feature/lens-core-bugfix-`; otherwise stop with `branch_scope_mismatch`.
   - Run `git status --short`. If implementation changes remain unstaged or uncommitted, commit them with a conventional commit message before continuing. Do not include unrelated user changes; stop and surface the blocker if unrelated changes are mixed into the same worktree.
   - Verify a non-empty implementation commit exists for this run. If no implementation commit can be established, stop with `bugfix_no_changes`.
   - Run `git -C {governance_repo} status --short`. If this flow produced governance changes (for example bug artifact updates), stage, commit, and push those changes before continuing. Do not include unrelated user changes; stop and surface the blocker if unrelated changes are mixed.
   - Run `git -C {project-root} status --short`. If this flow produced control-repo changes that belong to the bugfix execution, stage, commit, and push those changes on the active branch before continuing. Do not include unrelated user changes; stop and surface the blocker if unrelated changes are mixed.
   - Run `git rev-parse --short HEAD` and capture the result as `commit hash`.
   - Re-run the standard Lens push command from step 6 with `--branch {working_branch}` to verify the branch is pushed. If it exits non-zero, stop and surface the exact error.
   - Verify `origin/{working_branch}` exists after push verification. If not, stop and surface the blocking command/error.
   - Verify governance and control repos are clean for changes introduced by this flow after required pushes complete.
   - Re-run the idempotent PR creation command from step 7, capture `pr_url`, and include it as `PR URL`. The command must reuse an existing open PR when present.
   - If `pr_url` is empty after PR creation/reuse, stop and surface `pr_creation_failed`.
   - Re-run `record-quickdev-pr` with `bug_slug` and the final `pr_url`, capture the returned `path`, and use it as `bug_artifact_path` until closeout completes.
   - Re-run `close-quickdev-bug` with `bug_slug`, a concise change summary, and validation summary. Capture the returned `path` as the final `bug_artifact_path`, and verify it points under `bugs/Fixed/`.
   - If the user requested automatic completion after the dev cycle, invoke `lens-complete` after the target PR is recorded. The conductor must run `complete-ops.py finalize --control-repo {project-root} --confirm` for the active feature, commit and push governance archival changes, and include the completion result or structured blocker in the final response.
   - For automatic completion requests, switch the control repo to `{feature_id}-dev` before the completion handoff and rely on `complete-ops.py` to validate related branches, create and merge the `{feature_id}-dev` → `main` PR, and delete related control branches after merge.
   - Do not answer with the Output Contract until `working_branch`, `commit hash`, `PR URL`, and `bug_artifact_path` are all non-empty, the PR URL has been recorded in the bug artifact, the Core Bugfix closeout section documents the changes and validation, the bug artifact is under `bugs/Fixed/`, and the target repo has no uncommitted implementation changes.
   - Do not answer with the Output Contract if governance/control-repo changes created by this flow remain uncommitted or unpushed.
   - Never say "left uncommitted", "you can create the PR", or equivalent manual handoff language for this flow. Either complete commit/push/PR verification or surface the exact blocking command/error.

## Output Contract

Return:

- bug artifact path
- branch name
- commit hash
- PR URL
- concise change summary
- validation summary
