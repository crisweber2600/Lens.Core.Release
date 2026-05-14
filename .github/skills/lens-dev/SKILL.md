---
name: lens-dev
description: Dev phase conductor for epic and story implementation in a clean-room target repo. Use when the user requests dev, implement stories, or continue sprint execution.
---

## Follow-up Questions

Use `vscode_askQuestions` for all follow-up questions instead of freeform chat prompts.

# Lens Dev Skill

## Overview

This skill orchestrates Dev-phase execution for a feature after FinalizePlan approval. It prepares the target-repo branch context, resolves the active epic/story queue, delegates implementation work, and records checkpoint status in the feature docs session file.

Scope for this skill is lifecycle orchestration only. Story implementation logic is delegated to implementation-capable skills and tools.

## Input Contract

Required inputs:
- feature_id: Active feature identifier.
- governance_repo: Absolute path to governance repository.
- control_repo: Absolute path to control repository.

Optional inputs:
- target_repo_path: Explicit target repo path override.
- epic: Epic selector (number or id) to narrow execution to stories belonging to that epic.
  Omit this input to run without epic filtering.
  The values `all` and `all stories` are sentinels meaning "no epic filter" — they behave
  the same as omitting `epic` and do not filter the story queue to a literal `all` prefix.
  To run all sprints with auto-continue, omit `epic` (or use the sentinel) and set
  `continue_across_sprints: true`.
- continue_across_sprints: Boolean session flag set when the user explicitly requests `all stories`, `all sprints`, `run all the way through`, or automatic post-dev completion.
- base_branch: Branch to fork from when branch prep is needed.
- working_branch: Existing branch to resume if already prepared.

Preconditions:
- FinalizePlan artifacts exist and are review-ready.
- Governance feature state is readable.
- Control repo can check out the feature dev branch before reading feature docs.
- Target repo is reachable and has no unresolved merge state.

## Output Contract

Primary outputs:
- Dev execution summary for the selected epic/story scope.
- Story-level commit references for completed implementation slices.
- Updated dev-session state (completed, failed, blocked story lists).

Secondary outputs:
- Focused test execution result for each completed story slice.
- Final PR readiness signal when all required stories are complete.

## Error Behavior

Hard-stop errors:
- Missing required inputs or unresolved feature context.
- Control repo dev branch checkout failure.
- FinalizePlan gate not satisfied.
- Target repo branch prep failure.
- Commit/push failure for a completed story slice.

Recoverable errors:
- Story-level test failure: mark story failed and continue to next unblocked story only when user-approved.
- Missing optional inputs: prompt for values and continue.

Never continue silently after a hard-stop error.

## Test Hooks

Validate this contract with focused tests that assert:
- Required input keys are named in this skill.
- Output contract includes story commit references and dev-session updates.
- Control repo `{feature_id}-dev` branch activation is required before phase entry story validation.
- Governance repo resolution prefers `.lens/governance-setup.yaml` and forbids sibling-probing fallbacks.
- Hard-stop and recoverable error categories are explicitly documented.
- Scope statement keeps this skill orchestration-only.

## Governance Repo Resolution

Before Control Dev Branch Activation or any Phase Entry Validation, the conductor MUST resolve `governance_repo` deterministically:

1. Use an explicit `governance_repo` input when provided.
2. Otherwise read `{project-root}/.lens/governance-setup.yaml`; if it contains `governance_repo_path`, use that path.
3. Otherwise load `{project-root}/lens.core/_bmad/lens-work/bmadconfig.yaml`; if it contains `governance_repo_path`, use that path.
4. If `governance_repo` remains unset, stop with `config_missing` and do not read feature state.

The conductor MUST NOT probe sibling governance clone candidates such as `TargetProjects/lens/lens-governance` or choose a hardcoded default when `.lens/governance-setup.yaml` names a different governance repo. All `feature-yaml`, `lens-constitution`, `lens-git-orchestration`, and `lens-complete` calls in the dev flow MUST use the resolved `governance_repo`. Report the resolved path before reading `feature.yaml`.

## Control Dev Branch Activation

Before any Phase Entry Validation that reads `sprint-status.yaml`, story files, or other feature docs, the conductor MUST ensure the control repo is on the feature dev branch for the active feature.

1. Resolve `feature_id` from the explicit input, active session context, or governance feature selection before reading control-repo feature docs.
2. Set `control_dev_branch = {feature_id}-dev`.
3. Inspect the current control-repo branch with `git -C {control_repo} branch --show-current`.
4. If the current branch is not `control_dev_branch`, attempt to check out the dev branch:
   - Prefer an existing local `control_dev_branch` when present.
   - Otherwise fetch and check out `origin/{control_dev_branch}` when present.
   - Run `git -C {control_repo} pull --ff-only origin {control_dev_branch}` after checkout when the remote exists.
5. If checkout or pull fails, emit `control_dev_branch_checkout_failed` hard-stop with the attempted branch and git error. Do not proceed to `sprint_status_missing`, `story_file_missing`, or story queue validation while still on the wrong branch.
6. If checkout succeeds, use the docs on `control_dev_branch` as the source for all Phase Entry Validation and dev-cycle docs updates.

This branch activation is mandatory for `/lens-dev` because finalized planning docs are delivered on `{feature_id}-dev`. A `story_file_missing` result from `main`, `{feature_id}`, `{feature_id}-plan`, or any unrelated branch is not authoritative until this dev-branch activation has succeeded.

## Phase Entry Validation

After Control Dev Branch Activation succeeds, the conductor MUST validate all of the following. Fail fast on any violation.

1. **feature.yaml phase gate**: Read `feature.yaml` from the governance repo. The `phase` field MUST be `finalizeplan-complete`. If the phase is any other value:
   - If phase is `dev` or `dev-complete`: Resume dev execution from the recorded `dev-session.yaml` checkpoint.
   - If phase is any other value: Emit `phase_gate_failed` hard-stop with the current phase value; do not proceed.

2. **Sprint-status.yaml exists**: The file `docs/{domain}/{service}/{featureId}/sprint-status.yaml` MUST exist in the control repo. Missing file → `sprint_status_missing` hard-stop.

3. **Story files present**: Every story referenced by sprint-status.yaml MUST have a corresponding story file in the feature docs directory. Missing story file → `story_file_missing` hard-stop with the missing story id.

4. **Target repo reachable**: The target repo path must exist and `git status` must return cleanly (no unresolved merge conflicts). Merge conflict state → `target_repo_conflict` hard-stop.

5. **dev-session.yaml not corrupted**: If `dev-session.yaml` exists in the feature docs path, parse it as YAML. Parse failure → `dev_session_corrupted` hard-stop.

## Constitution Hard Gate Enforcement

After Phase Entry Validation succeeds and before the Story Execution Loop begins, the conductor MUST load and enforce the domain constitution.

Load `{project-root}/lens.core/_bmad/lens-work/skills/lens-constitution/SKILL.md` and invoke:
`lens-constitution resolve --governance-dir {governance_repo}`

If the constitution fails to resolve (missing required org level or parse error), stop immediately and report: "Constitution resolution failed for domain={domain} service={service}. Hard gate enforcement requires a valid constitution — run /new-domain or /new-service to scaffold missing levels." Do not proceed to the story execution loop.

**Constitution Hard Gate Enforcement:** After resolving the constitution, extract all hard-gate requirements from the full resolved output — both structured fields (`gate_mode: hard`, `required_artifacts`, `enforce_stories`, `enforce_review`) and all prose articles. These requirements are **mandatory implementation constraints** for all stories in this dev session. Before the Story Execution Loop:
- Display the applicable hard-gate requirements to the operator.
- Pass the full resolved constitution prose as required context to every implementation delegate (e.g., Article 7 TDD red-green, Article 8 BDD GWT scenarios per AC, Article 9 security credential docs).
- If a story's implementation plan or acceptance criteria would violate any hard-gate requirement, stop and report the violation list. Do not delegate and do not begin story implementation until all violations are resolved.

## Story File Validation

Before delegating a story for execution, validate that the story file is actionable. Accept either the canonical dev-ready packet or the FinalizePlan story packet produced by this lifecycle:
- Context: `Context` section with non-empty description, or FinalizePlan `Goal` plus `Scope` sections.
- Implementation instructions: `Implementation Steps` section with at least one numbered step, or FinalizePlan `Files To Produce` plus `Notes For Dev` and/or `Scope` content that names concrete paths or actions.
- Acceptance criteria: `Acceptance Criteria` section with at least one `[ ]` checkbox, or FinalizePlan `Acceptance` bullets. Checkbox-less FinalizePlan `Acceptance` bullets are valid acceptance criteria and must be passed to the implementation delegate.
- Dev record: `Dev Agent Record` section when present. If an otherwise valid FinalizePlan story packet omits `Dev Agent Record`, append `## Dev Agent Record` before delegation as part of the normal control-repo docs update; do not hard-stop solely for this missing section.

Any missing canonical section or accepted FinalizePlan alias content → `story_file_invalid` hard-stop with the missing content category and story id.

Additionally, validate that the story file includes the `Governance Coordination Note` section if the story's `type` is `new` or `fix`. Missing governance note on new/fix stories → `governance_note_missing` warning (not hard-stop); log and continue.

## Story Queue Resolution

After phase entry passes:

1. Parse `sprint-status.yaml`. Stories are iterable items; each has at minimum `story_id`, `status`, and optionally `blocked_by`.
2. Build the **ready queue** from stories where all `blocked_by` entries are in the `completed` list of `dev-session.yaml` and the status is queueable. Queueable statuses are:
   - `ready`.
   - `not-started` when this is the first dev session for a FinalizePlan packet, or when the story is not already listed in `dev-session.yaml` as completed, failed, or blocked. Treat these FinalizePlan `not-started` stories as initially ready for dev and update them to `in-progress` immediately before delegation.
3. If the `epic` input is set to a specific epic number or id, filter the ready queue to stories matching that epic prefix. The sentinel values `all` and `all stories` are treated the same as omitting `epic` — no epic filtering is applied; they do not filter the queue to a literal `all` prefix.
4. If the ready queue is empty and there are stories in `status == 'in-progress'` from a prior session: re-enqueue those stories as `ready` (crash recovery).
5. If the ready queue is empty and no stories remain in `ready`, `not-started`, or `in-progress`: the sprint is **complete**. Emit `sprint_complete` signal and update `feature.yaml` phase to `dev-complete`, then run the complete cycle automatically when the invocation requested post-dev completion.

## Sprint Boundary Policy

After completing every story in the ready queue for the current sprint, emit a `sprint_boundary` checkpoint.

Default behavior:
- For normal sprint-scoped or epic-scoped invocations, the conductor MUST wait for explicit user confirmation before advancing to the next sprint.
- This default pause protects users from accidentally starting another sprint of target-repo work.

All-stories behavior:
- When the invocation explicitly requests `all stories`, `all sprints`, `run all the way through`, or automatic post-dev completion, set `continue_across_sprints: true` in session context before the first story loop.
- In that mode, the original invocation is the explicit confirmation to cross sprint boundaries. The conductor MUST record the `sprint_boundary` checkpoint and immediately resolve the next unblocked sprint queue without rendering a numbered continue/stop menu.
- Continue across sprint boundaries until every story in the selected scope is `done`, or until a hard-stop error, test failure, failed story, or blocked story requires user intervention.
- The conductor MUST NOT stop merely because the current sprint completed while `continue_across_sprints: true` and additional unblocked stories remain.

The pause message must include:
- Stories completed in this sprint.
- Next sprint number and story count.
- Any stories that failed or were blocked.

## Story Execution Loop

For each story in the ready queue (in dependency order):

1. **Update sprint-status.yaml**: Set story status to `in-progress`; commit and push control repo.
2. **Validate story file** (per Story File Validation above).
3. **Delegate to implementation skill**: Pass the story file path, target repo context, and feature context to the implementation delegate.
4. **Run focused tests**: After implementation, run `python -m pytest` in the target repo scoped to the story's test files. Capture pass/fail summary.
5. **Commit and push**: Commit the story implementation to the target repo branch with message `[{storyId}][{epicLabel}] {storyTitle}`. Push to remote.
6. **Record in dev-session.yaml**: Add story to `stories_completed` (or `stories_failed`), increment `current_story_index`, update `last_checkpoint` timestamp.
7. **Update sprint-status.yaml**: Set story status to `done` (or `failed`); commit and push control repo.
8. **Pause if user-requested** or on test failure (per Recoverable Errors above).

## dev-session.yaml Contract

The conductor reads and writes `dev-session.yaml` in the feature docs directory:

```yaml
feature_id: {featureId}
epic_number: {epicNumber or 'all'}
working_branch: {branch}
base_branch: {baseBranch}
total_stories: {count}
stories_completed: [{storyId}, ...]
stories_failed: [{storyId}, ...]
stories_blocked: [{storyId}, ...]
current_story_index: {0-based index}
last_checkpoint: '{ISO8601 timestamp}'
status: in-progress | sprint-complete | complete
requires_final_pr: true | false
final_pr_url: null | {url}
```

All timestamps are ISO 8601. All writes emit this schema exactly. Read-time compatibility for old formats is handled by the dev-session compatibility layer (see `scripts/dev-session-compat.py`).

## Execution Flow

1. **Control dev branch activation**: Resolve the active feature and switch the control repo to `{feature_id}-dev` before reading `sprint-status.yaml` or story files.
2. **Phase entry validation**: Validate feature.yaml phase, sprint-status.yaml, story files, target repo state, and dev-session.yaml integrity on `{feature_id}-dev`.
3. **Constitution hard gate enforcement**: Load and enforce domain constitution; extract hard gates; stop if any violation would be introduced. Pass constitution constraints to all implementation delegates.
4. **Story queue resolution**: Build ready queue from sprint-status.yaml and dev-session.yaml completed list.
5. **Branch context**: Confirm or prepare target repo branch via `lens-git-orchestration`.
6. **Story loop**: For each ready story, validate, delegate, test, commit, record, and advance.
7. **Sprint boundary**: Record a boundary checkpoint after each sprint. Pause for user confirmation by default; continue automatically when `continue_across_sprints: true` was set by an explicit all-stories/all-sprints/auto-complete invocation.
8. **Completion**: When all stories are done, emit `sprint_complete` and update `feature.yaml` to `dev-complete`. If the invocation requested automatic post-dev completion, immediately run `lens-complete` preconditions and then `complete-ops.py finalize --control-repo {control_repo} --confirm`; treat the user's auto-complete request as the explicit confirmation for that finalize call. If completion preconditions fail, surface the structured blocker and do not simulate completion.

## Automatic Complete Handoff

When a dev invocation includes an explicit post-dev completion request, the conductor MUST:

1. Finish all normal dev closing actions first: story statuses, target repo commits, target PR, and `feature.yaml` phase `dev-complete`.
2. Check out or create the control repo `{feature_id}-dev` branch and keep it as the working branch for dev-cycle docs delivery.
3. Invoke the complete runtime from the installed module path:

```bash
uv run --script lens.core/_bmad/lens-work/skills/lens-complete/scripts/complete-ops.py finalize \
   --governance-repo {governance_repo} \
   --feature-id {feature_id} \
   --control-repo {control_repo} \
   --confirm
```

4. Commit and push governance archive changes to `main` after a successful finalize response.
5. The complete runtime validates `{feature_id}-plan` -> `{feature_id}` -> `{feature_id}-dev`, merges `{feature_id}-dev` into `main`, and deletes the related control branches after a successful merge. Surface any `control_repo_merge_failed` warning from the complete runtime; do not report completion as blocked if governance archival succeeded.

## Integration Points

- lens-feature-yaml: read feature state and docs metadata.
- lens-git-state: verify repo/branch status before each story.
- lens-git-orchestration: branch prep and git safety operations.
- lens-constitution: load and enforce domain constitution hard gates before story execution.
- lens-bmad-skill: delegated implementation and review actions.
- scripts/dev-session-compat.py: read-time compatibility for old dev-session.yaml formats.
