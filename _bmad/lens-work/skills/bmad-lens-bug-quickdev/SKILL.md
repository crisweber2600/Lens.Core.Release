---
name: bmad-lens-bug-quickdev
description: Bug quick-dev conductor. Takes one bug report, records bug intake, then runs quick-dev implementation in target project with required git and PR flow.
---

# /lens-bug-quickdev

## Overview

`/lens-bug-quickdev` is a single-bug execution flow for direct implementation.
It captures one bug report, records a governance bug artifact, and then delegates
implementation to quick-dev in the target project.

This skill is a thin conductor. It orchestrates inputs and delegation only.

## Non-Negotiables

- Revert any no-implicit-commit behavior for this flow: if this run writes changes in a touched repo, commit and push them before final response.
- Never leave implementation, governance, or control-repo changes uncommitted as a manual handoff.
- Never tell the user to commit, push, or open the PR themselves when the required automation commands are available.
- The complete target-project workflow is mandatory: checkout/pull base, create or reuse the QuickDev branch, implement, validate, commit, push, create or reuse the PR, document the changes, and close the QuickDev bug artifact.

## Required Inputs

Collect these fields before execution:

- `title`
- `description`
- `repro_steps`
- `expected`
- `actual`

If any field is missing, ask only for missing fields and stop until complete.

## Branch Continuation Rule

- If the user follow-up is an extension of the same active ask, continue on the existing branch from the most recent `/lens-bug-quickdev` run.
- In continuation mode, reuse the prior `working_branch` and derive both `feature_id` and `feature_slug` from it by removing the `feature/` prefix.
- Do not create a new feature branch in continuation mode. The follow-up must stay on the same branch.
- Only derive `feature_id = bugfix-{bug-title-slug}` and `feature_slug = bugfix-{bug-title-slug}` for a new, independent ask.

## On Activation

1. Ensure prompt-start preflight already succeeded.
2. Resolve:
   - `governance_repo = {project-root}/TargetProjects/lens/lens-governance`
   - `target_project = {project-root}/TargetProjects/lens-dev/new-codebase/lens.core.src`
   - `legacy_project = {project-root}/TargetProjects/lens-dev/old-codebase/lens.core.src`
3. Resolve branch context before any target-repo implementation:
   - If this is a continuation follow-up, capture the prior `working_branch` from the most recent `/lens-bug-quickdev` output in the current conversation.
   - In continuation mode, set `feature_id` and `feature_slug` to the prior branch name without the `feature/` prefix.
   - Otherwise set `feature_id = bugfix-{bug-title-slug}` and `feature_slug = bugfix-{bug-title-slug}`.
4. Create bug intake artifact:

```bash
uv run --script lens.core/_bmad/lens-work/scripts/bug-reporter-ops.py create-bug \
  --title "{title}" \
  --description "{description}\n\nRepro Steps:\n{repro_steps}\n\nExpected:\n{expected}\n\nActual:\n{actual}" \
  --chat-log "Bug report submitted via /lens-bug-quickdev." \
  --governance-repo {governance_repo} \
  --queue QuickDev
```

5. Parse script JSON:
   - `status: created` or `status: duplicate` are both valid; continue.
   - Capture `slug` as `bug_slug` and `path` as `bug_artifact_path` for the PR-recording step and Output Contract.
   - On non-zero exit, stop and surface error.
6. Load and run `{project-root}/.github/skills/bmad-quick-dev/SKILL.md`.
7. Use this implementation intent exactly:

"Fix this bug report in `TargetProjects/lens-dev/new-codebase/lens.core.src`.
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
    Capture `working_branch` from the JSON output and use it for all subsequent target-repo validation, push, and PR steps. If this command exits non-zero, stop and surface the exact error.
   In continuation mode, `working_branch` must match the previously active branch; if it does not, stop and surface the mismatch.
   This command is mandatory because it checks out the base branch, pulls the base branch, and creates or reuses the QuickDev working branch. Do not replace it with narrative instructions or skip it when the target repo already appears to be on a usable branch.
2) Before implementing, identify the primary affected Lens command and inspect the same command in `TargetProjects/lens-dev/old-codebase/lens.core.src` to understand legacy behavior and identify gaps. Use the same command name and closest matching prompt/skill/script entrypoint when available. If no legacy match exists, record that as a gap.
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
     --title "fix(lens): {title}" \
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
    Then document the changes and close out the QuickDev bug by executing this terminal command from the workspace root:
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
     --title "fix(lens): {title}" \
     --body "{bug_context_with_legacy_gap_notes_and_validation_summary}"
   ```
    Capture the PR URL from the `gh pr create` output, then execute the same `record-quickdev-pr` and `close-quickdev-bug` commands above with the captured PR URL. Do NOT ask the user to create the PR themselves."

8. After quick-dev delegation returns, run this conductor completion gate before responding to the user. This gate is mandatory even if the delegate claims the work is complete:
   - Verify the target project is still on `{working_branch}`.
   - Run `git status --short`. If implementation changes remain unstaged or uncommitted, commit them with a conventional commit message before continuing. Do not include unrelated user changes; stop and surface the blocker if unrelated changes are mixed into the same worktree.
   - Run `git -C {governance_repo} status --short`. If this flow produced governance changes (for example bug artifact updates), stage, commit, and push those changes before continuing. Do not include unrelated user changes; stop and surface the blocker if unrelated changes are mixed.
   - Run `git -C {project-root} status --short`. If this flow produced control-repo changes that belong to the bugfix execution, stage, commit, and push those changes on the active branch before continuing. Do not include unrelated user changes; stop and surface the blocker if unrelated changes are mixed.
   - Run `git rev-parse --short HEAD` and capture the result as `commit hash`.
   - Re-run the standard Lens push command from step 6 with `--branch {working_branch}` to verify the branch is pushed. If it exits non-zero, stop and surface the exact error.
   - Verify governance and control repos are clean for changes introduced by this flow after required pushes complete.
   - Re-run the idempotent PR creation command from step 7, capture `pr_url`, and include it as `PR URL`. The command must reuse an existing open PR when present.
   - Re-run `record-quickdev-pr` with `bug_slug` and the final `pr_url`, capture the returned `path`, and use it as `bug_artifact_path` until closeout completes.
   - Re-run `close-quickdev-bug` with `bug_slug`, a concise change summary, and validation summary. Capture the returned `path` as the final `bug_artifact_path`, and verify it points under `bugs/Fixed/`.
   - If the user requested automatic completion after the dev cycle, invoke `lens-complete` after the target PR is recorded. The conductor must run `complete-ops.py finalize --control-repo {project-root} --confirm` for the active feature, commit and push governance archival changes, and include the completion result or structured blocker in the final response.
   - For automatic completion requests, switch the control repo to `{feature_id}-dev` before the completion handoff and rely on `complete-ops.py` to validate related branches, create and merge the `{feature_id}-dev` → `main` PR, and delete related control branches after merge.
   - Do not answer with the Output Contract until `working_branch`, `commit hash`, `PR URL`, and `bug_artifact_path` are all non-empty, the PR URL has been recorded in the bug artifact, the QuickDev closeout section documents the changes and validation, the bug artifact is under `bugs/Fixed/`, and the target repo has no uncommitted implementation changes.
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
