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

## Required Inputs

Collect these fields before execution:

- `title`
- `description`
- `repro_steps`
- `expected`
- `actual`

If any field is missing, ask only for missing fields and stop until complete.

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
  --chat-log "Bug report submitted via /lens-bug-quickdev." \
  --governance-repo {governance_repo} \
  --queue QuickDev
```

4. Parse script JSON:
   - `status: created` or `status: duplicate` are both valid; continue.
   - Capture `slug` as `bug_slug` and `path` as `bug_artifact_path` for the PR-recording step and Output Contract.
   - On non-zero exit, stop and surface error.
5. Load and run `{project-root}/.github/skills/bmad-quick-dev/SKILL.md`.
6. Use this implementation intent exactly:

"Fix this bug report in `TargetProjects/lens-dev/new-codebase/lens.core.src`.
Title: {title}
Description: {description}
Repro Steps: {repro_steps}
Expected: {expected}
Actual: {actual}

Required workflow in target project:
1) `git checkout develop`
2) `git pull`
3) `git checkout -b feature/bugfix-{bug-title-slug}`
4) Before implementing, identify the primary affected Lens command and inspect the same command in `TargetProjects/lens-dev/old-codebase/lens.core.src` to understand legacy behavior and identify gaps. Use the same command name and closest matching prompt/skill/script entrypoint when available. If no legacy match exists, record that as a gap.
5) If the legacy comparison reveals large gaps that materially change expected behavior, workflow, or outputs, stop and use `vscode_askQuestions` to confirm user intent before implementing.
6) Implement the fix and run relevant validation
7) `git add` and `git commit` with conventional commit message
8) `git push -u origin <branch>`
9) Create the PR by executing this terminal command from the workspace root — you MUST execute this command, not narrate it:
   ```bash
   uv run --script lens.core/_bmad/lens-work/skills/lens-git-orchestration/scripts/git-orchestration-ops.py create-pr \
     --repo {target_project} \
     --governance-repo {governance_repo} \
     --head feature/bugfix-{bug-title-slug} \
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
    Capture the returned `path` as the final `bug_artifact_path` and include it in the Output Contract response. If this command exits non-zero, stop and surface the exact error.
    If the create-pr command exits non-zero, surface the exact error and run this fallback from the `{target_project}` directory:
   ```bash
   gh pr create \
     --base develop \
     --head feature/bugfix-{bug-title-slug} \
     --title "fix(lens): {title}" \
     --body "{bug_context_with_legacy_gap_notes_and_validation_summary}"
   ```
   Capture the PR URL from the `gh pr create` output, then execute the same `record-quickdev-pr` command above with the captured PR URL. Do NOT ask the user to create the PR themselves."

7. After quick-dev delegation returns, run this conductor completion gate before responding to the user. This gate is mandatory even if the delegate claims the work is complete:
   - Verify the target project is still on `feature/bugfix-{bug-title-slug}`.
   - Run `git status --short`. If implementation changes remain unstaged or uncommitted, commit them with a conventional commit message before continuing. Do not include unrelated user changes; stop and surface the blocker if unrelated changes are mixed into the same worktree.
   - Run `git rev-parse --short HEAD` and capture the result as `commit hash`.
   - Run `git push -u origin feature/bugfix-{bug-title-slug}` to verify the branch is pushed. If it exits non-zero, stop and surface the exact error.
   - Re-run the idempotent PR creation command from step 9, capture `pr_url`, and include it as `PR URL`. The command must reuse an existing open PR when present.
   - Re-run `record-quickdev-pr` with `bug_slug` and the final `pr_url`, capture the returned `path`, and use it as `bug_artifact_path`.
   - If the user requested automatic completion after the dev cycle, invoke `lens-complete` after the target PR is recorded. The conductor must run `complete-ops.py finalize --control-repo {project-root} --confirm` for the active feature, commit and push governance archival changes, and include the completion result or structured blocker in the final response.
   - For automatic completion requests, switch the control repo to `{feature_id}-dev` before the completion handoff and rely on `complete-ops.py` to validate related branches, create and merge the `{feature_id}-dev` → `main` PR, and delete related control branches after merge.
   - Do not answer with the Output Contract until `commit hash`, `PR URL`, and `bug_artifact_path` are all non-empty, the PR URL has been recorded in the bug artifact, and the target repo has no uncommitted implementation changes.
   - Never say "left uncommitted", "you can create the PR", or equivalent manual handoff language for this flow. Either complete commit/push/PR verification or surface the exact blocking command/error.

## Output Contract

Return:

- bug artifact path
- branch name
- commit hash
- PR URL
- concise change summary
- validation summary
