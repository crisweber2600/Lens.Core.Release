---
name: lens-nextlens-bugfix
description: Canonical NextLens bugfix conductor. Records a namespaced bug, prepares a fresh governed branch, delegates bounded implementation, and enforces commit and path gates before returning.
---

## Follow-up Questions

Use `vscode_askQuestions` for all follow-up questions instead of freeform chat prompts.

# /lens-nextlens-bugfix

## Overview

`/lens-nextlens-bugfix` is the single canonical Lens-owned NextLens bugfix surface.
It captures one NextLens runtime bug, records a namespaced bug artifact, resolves the governed
design context and fix spec, prepares a fresh target branch, delegates implementation, and then
finishes the conductor-owned push, PR recording, Doctor-backed validation capture, and bug closeout.

## Operator-Facing Boundaries

- The skill source and registration live in `TargetProjects/lens-dev/new-codebase/lens.core.src`.
- All NextLens implementation changes for this command must stay under `TargetProjects/nextlens/src/NextLens`, including existing runtime logic, `.agents/skills/` skill roots, `skills/module.yaml`, and NextLens setup assets when the bug warrants expanding the module surface.
- Use model judgment after inspecting the current NextLens repo surfaces to decide whether the bug is a bounded edit or a module-surface expansion that deserves a new skill. Do not reduce that decision to keyword spotting alone.
- This command must not bypass Lens governance, story selection, validation, or review gates.
- Preserve existing `/lens-core-bugfix` behavior as a separate command surface for Lens core bugs.
- The conductor owns branch preparation, push, PR creation, validation evidence capture, and bug closeout. The implementation delegate does not own push, PR, bug closeout, or final success reporting.

## Non-Negotiables

- Generate the governed handoff with `nextlens_fix_spec.py`; do not duplicate target-root or branch-name logic inline.
- The fix spec must resolve `allowed_write_root` to `TargetProjects/nextlens/src/NextLens` before any mutation or delegation.
- Derive `bugfix_feature_id = nextlens-bugfix-{bug_slug}`, `bugfix_feature_slug = nextlens-bugfix-{bug_slug}`, and `bugfix_working_branch = feature/nextlens-bugfix-{bug_slug}` from the stable `bug_slug`.
- Prepare the target branch through `git-orchestration-ops.py prepare-dev-branch` from the workspace root.
- If `prepare-dev-branch` exits non-zero, stop and surface the exact error. Treat `dirty_working_tree` as a hard blocker; do not auto-clean the target repo.
- Branch reuse for another bug is forbidden. If `reused` is true for a newly created bug artifact, stop with `branch_reuse_blocked` unless the reused branch exactly matches `feature/{bugfix_feature_id}` and is already known to belong to the same `bug_slug`.
- Capture `starting_head` immediately after branch preparation. On completion, if `HEAD` still matches `starting_head`, stop with `bugfix_no_changes`.
- Block any proposed or committed edit whose path resolves outside `allowed_write_root`.
- If the requested behavior warrants a new NextLens skill, author it inside `TargetProjects/nextlens/src/NextLens` through the local `bmad-module-builder`, use the local `bmad-workflow-builder` for companion workflow assets when needed, and update the NextLens install surfaces in the same repo so the capability is installable.
- Never ask the implementation delegate to push, open a PR, record a PR URL, close the bug artifact, or report final success. Those actions belong to the conductor completion gate.
- A successful run requires all of the following to be non-empty and verified: `working_branch`, `commit hash`, `PR URL`, and `bug_artifact_path` under `bugs/nextlens/Fixed/`.
- Reuse `bug-reporter-ops.py record-quickdev-pr` and `close-quickdev-bug`; do not invent a parallel NextLens closeout path.
- Reference NextLens Doctor output when it applies. If Doctor is not applicable or deferred, record that explicit rationale instead of silently omitting validation evidence.
- High or blocking Salmon-linked bugs require approved-route evidence showing closure used the governed NextLens closeout path.

## Input Contract

Collect these required inputs before any downstream execution:

- `what_happened`
- `what_should_have_happened`
- `chat_history`

If any required input is missing, ask only for the missing field(s) and stop.

## Operator Quick Reference

- Required inputs: `what_happened`, `what_should_have_happened`, and `chat_history`.
- Optional metadata: `severity`, `salmon_signal_id`, `evidence_refs`, `suspected_target_surface`, `validation_request`, and `operator_notes`.
- Expected outputs: `bug_artifact_path`, `bug_slug`, `working_branch`, `base_branch`, `commit_hash`, `PR URL`, concise validation summary, and the bounded changed-files summary.
- Required closeout evidence: recorded `PR URL`, NextLens Doctor status plus evidence or rationale, and approved-route evidence for high or blocking Salmon-linked bugs.

## Execution Contract

1. Confirm the request is a NextLens bug whose implementation stays inside `TargetProjects/nextlens/src/NextLens`, not a Lens core bug that requires edits in `TargetProjects/lens-dev/new-codebase/lens.core.src` or another non-NextLens repo.
2. Resolve feature context through approved authority before reading or writing anything:
   - explicit feature input when provided
   - session feature context when already set
   - `feature.yaml` authority as the final source
3. Resolve and restate the two write boundaries:
   - command source lives in `TargetProjects/lens-dev/new-codebase/lens.core.src`
  - NextLens implementation changes belong in `TargetProjects/nextlens/src/NextLens`
4. Generate the NextLens fix spec before creating the branch. Use `nextlens_fix_spec.py` so the conductor receives:
   - `bug_slug`
   - `bug_artifact_path`
   - `bug_reporter_fields`
   - `bugfix_feature_id`
   - `bugfix_feature_slug`
   - `bugfix_working_branch`
   - `allowed_write_root`
   - `allowed_write_root_display`
   - `delegation_blocked`
   - `delegation_blockers`
5. If the fix spec returns `delegation_blocked: true`, stop before mutation.
6. Create the namespaced bug artifact with `bug-reporter-ops.py create-bug` using the `bug_reporter_fields` returned by the fix spec. Continue only when the returned slug matches `bug_slug`.
7. Prepare the target repo branch before delegation by running this standard Lens git operation from the workspace root:

```bash
uv run --script lens.core/_bmad/lens-work/skills/lens-git-orchestration/scripts/git-orchestration-ops.py prepare-dev-branch \
  --repo {allowed_write_root} \
  --governance-repo {governance_repo} \
  --feature-id {bugfix_feature_id} \
  --feature-slug {bugfix_feature_slug} \
  --mode feature-id
```

8. Capture `working_branch`, `base_branch`, `created`, and `reused` from the JSON output. `working_branch` must equal `bugfix_working_branch` and must start with `feature/nextlens-bugfix-`; otherwise stop with `branch_scope_mismatch`.
9. Record `starting_head = git rev-parse HEAD` immediately after branch preparation and before delegation.
10. Delegate implementation only after the allowed target root resolves to `TargetProjects/nextlens/src/NextLens`. The implementation prompt must explicitly say:
    - edit only inside `{allowed_write_root}`
    - if any proposed edit resolves outside `{allowed_write_root}`, stop with `target_boundary_violation`
  - inspect the current NextLens repo surfaces and use model judgment to decide whether the bug is a bounded edit to existing files or a module-surface expansion that deserves a new skill; do not rely on keyword spotting alone
  - if a new NextLens skill is warranted, create it through the local `bmad-module-builder`, use the local `bmad-workflow-builder` when companion workflow assets are needed, and update install/discovery surfaces inside `{allowed_write_root}` including `skills/module.yaml` and the `bmad-nextlens-setup` assets
    - run focused validation for the touched NextLens surface and capture or reference NextLens Doctor output when it applies
    - create one conventional implementation commit in the target repo
    - do not push, create a PR, close the bug, or report final success
11. The conductor resumes immediately after the delegate returns. Do not treat the delegate summary as success until the completion gate passes.

## Conductor Completion Gate

Run this gate immediately after the implementation delegate returns:

- Verify the target repo is still on `working_branch`.
- Run `git status --short` in `{allowed_write_root}`. If the worktree is dirty after delegation, stop with the exact blocker rather than silently committing or ignoring it.
- Run `git rev-parse --short HEAD` and capture the result as `commit_hash`.
- Compare the final `HEAD` to `starting_head`. If they are identical, stop with `bugfix_no_changes`. No-op completion is forbidden.
- List files changed since `starting_head`. If the change set is empty, stop with `bugfix_no_changes`.
- Validate every changed path stays under `{allowed_write_root}`. If any path escapes the approved target root, stop with `target_boundary_violation`.
- If the implementation delegate returns without a target commit, stop with `bugfix_no_changes`.
- Re-run the standard Lens push command from the workspace root and verify the branch is pushed:
  ```bash
  uv run --script lens.core/_bmad/lens-work/skills/lens-git-orchestration/scripts/git-orchestration-ops.py push \
    --repo {allowed_write_root} \
    --governance-repo {governance_repo} \
    --branch {working_branch}
  ```
  If this exits non-zero, stop and surface the exact error.
- Verify `origin/{working_branch}` exists after push. If not, stop and surface the blocking error.
- Run the idempotent PR creation command from the workspace root, capture `pr_url`, and include it as `PR URL`. The command must create or reuse the active PR:
  ```bash
  uv run --script lens.core/_bmad/lens-work/skills/lens-git-orchestration/scripts/git-orchestration-ops.py create-pr \
    --repo {allowed_write_root} \
    --governance-repo {governance_repo} \
    --head {working_branch} \
    --base {base_branch} \
    --title "fix(nextlens): {bug_reporter_fields.title}" \
    --body "{validation_summary_with_doctor_and_bug_context}"
  ```
  If this command exits non-zero, run this fallback from `{allowed_write_root}`:
  ```bash
  gh pr create \
    --base {base_branch} \
    --head {working_branch} \
    --title "fix(nextlens): {bug_reporter_fields.title}" \
    --body "{validation_summary_with_doctor_and_bug_context}"
  ```
  Capture the PR URL from whichever command succeeds. Do NOT ask the user to create the PR themselves.
- If `pr_url` is empty after both attempts, stop with `pr_creation_failed`.
- Run `record-quickdev-pr` with `bug_slug`, `pr_url`, and `--namespace nextlens`, capture the returned `path`, and use it as `bug_artifact_path`:
  ```bash
  uv run --script lens.core/_bmad/lens-work/scripts/bug-reporter-ops.py record-quickdev-pr \
    --governance-repo {governance_repo} \
    --slug {bug_slug} \
    --pr-url "{pr_url}" \
    --namespace nextlens
  ```
- Capture Doctor evidence from the validation output instead of reimplementing Doctor checks. If Doctor passed, record `--doctor-status passed` with `--doctor-evidence "{doctor_output_reference}"`. If Doctor is not applicable or deferred, record `--doctor-status not-applicable|deferred` with `--doctor-rationale "{doctor_rationale}"`.
- Run `close-quickdev-bug` with `bug_slug`, a concise change summary, validation summary, and the Doctor status/evidence. Capture the returned `path` as the final `bug_artifact_path`, and verify it points under `bugs/nextlens/Fixed/`:
  ```bash
  uv run --script lens.core/_bmad/lens-work/scripts/bug-reporter-ops.py close-quickdev-bug \
    --governance-repo {governance_repo} \
    --slug {bug_slug} \
    --summary "{concise_change_summary}" \
    --validation-summary "{validation_summary}" \
    --namespace nextlens \
    --doctor-status {doctor_status} \
    --doctor-evidence "{doctor_output_reference}" \
    --doctor-rationale "{doctor_rationale}"
  ```
- If Doctor validation evidence or an allowed not-applicable/deferred rationale is missing, stop and do not move the artifact.
- Do not answer with the Output Contract until `working_branch`, `commit_hash`, `PR URL`, and `bug_artifact_path` are all non-empty, the PR URL has been recorded on the namespaced bug artifact, the QuickDev Closeout section documents the change summary plus Doctor evidence/rationale, and the bug artifact is under `bugs/nextlens/Fixed/`.

## Output Contract

Return:

- canonical command name: `lens-nextlens-bugfix`
- `bug_artifact_path`
- `bug_slug`
- `working_branch`
- `base_branch`
- `commit_hash`
- `PR URL`
- concise validation summary
- changed files summary scoped to `TargetProjects/nextlens/src/NextLens`
- boundary reminder for source vs runtime paths
- Doctor evidence reference or explicit not-applicable/deferred rationale

## Error Behavior

- If the report actually requires changes in `TargetProjects/lens-dev/new-codebase/lens.core.src` or another non-NextLens repo, direct the operator to `/lens-core-bugfix`. Do not treat new NextLens skill or install-surface work inside `TargetProjects/nextlens/src/NextLens` as a Lens core bug.
- If `dirty_working_tree`, `branch_reuse_blocked`, `branch_scope_mismatch`, `target_boundary_violation`, `bugfix_no_changes`, `pr_creation_failed`, missing PR evidence, or missing Doctor evidence/rationale occurs, stop with the exact blocker and do not report success.
- If the request asks to reuse a branch from a different bug, stop with `branch_reuse_blocked`.
- If required inputs are missing, stop after requesting only the missing inputs.

## Test Hooks

- Prompt wrappers exist at `.github/prompts/lens-nextlens-bugfix.prompt.md` and `_bmad/lens-work/prompts/lens-nextlens-bugfix.prompt.md`.
- `module.yaml` registers `lens-nextlens-bugfix.prompt.md` and `lens-nextlens-bugfix` exactly once.
- Help metadata includes one canonical `lens-nextlens-bugfix` row with the required inputs, optional Salmon metadata, fresh branch delegation, runtime boundary path, `PR URL`, and Doctor-backed closeout evidence.
- Contract guidance must tell the implementation delegate to use model judgment, not keyword spotting alone, when deciding whether a NextLens bug deserves a new skill and install-surface updates inside `TargetProjects/nextlens/src/NextLens`.
- Validation hooks must fail with actionable blockers when `nextlens_fix_spec.py`, `bug-reporter-ops.py`, docs context access, target repo resolution, namespace `nextlens`, or `allowed_write_root` boundary enforcement drift.
- Expected blocker text includes `NextLens docs context is incomplete or conflicting`, `does not include 'NextLens'`, `includes multiple 'NextLens' entries`, and `target_boundary_violation`.
- Contract tests must cover branch identity, no-op completion, push/PR recording, Doctor-backed closeout, target boundary enforcement, and dirty-worktree or branch-reuse blockers.
