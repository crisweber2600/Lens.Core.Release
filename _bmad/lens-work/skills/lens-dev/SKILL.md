---
name: lens-dev
description: Dev phase conductor for epic and story implementation in a clean-room target repo. Use when the user requests dev, implement stories, or continue sprint execution.
---

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
- epic: Epic selector (number or id) when the user narrows execution.
- base_branch: Branch to fork from when branch prep is needed.
- working_branch: Existing branch to resume if already prepared.

Preconditions:
- FinalizePlan artifacts exist and are review-ready.
- Governance feature state is readable.
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
- Hard-stop and recoverable error categories are explicitly documented.
- Scope statement keeps this skill orchestration-only.

## Phase Entry Validation

Before execution begins, the conductor MUST validate all of the following. Fail fast on any violation.

1. **feature.yaml phase gate**: Read `feature.yaml` from the governance repo. The `phase` field MUST be `finalizeplan-complete`. If the phase is any other value:
   - If phase is `dev` or `dev-complete`: Resume dev execution from the recorded `dev-session.yaml` checkpoint.
   - If phase is any other value: Emit `phase_gate_failed` hard-stop with the current phase value; do not proceed.

2. **Sprint-status.yaml exists**: The file `docs/{domain}/{service}/{featureId}/sprint-status.yaml` MUST exist in the control repo. Missing file → `sprint_status_missing` hard-stop.

3. **Story files present**: Every story referenced by sprint-status.yaml MUST have a corresponding story file in the feature docs directory. Missing story file → `story_file_missing` hard-stop with the missing story id.

4. **Target repo reachable**: The target repo path must exist and `git status` must return cleanly (no unresolved merge conflicts). Merge conflict state → `target_repo_conflict` hard-stop.

5. **dev-session.yaml not corrupted**: If `dev-session.yaml` exists in the feature docs path, parse it as YAML. Parse failure → `dev_session_corrupted` hard-stop.

## Story File Validation

Before delegating a story for execution, validate the story file has all required sections:
- `Context` section: Non-empty description.
- `Implementation Steps` section: At least one numbered step.
- `Acceptance Criteria` section: At least one criterion with a `[ ]` checkbox.
- `Dev Agent Record` section: Present (may be empty at this point).

Any missing section → `story_file_invalid` hard-stop with the missing section name and story id.

Additionally, validate that the story file includes the `Governance Coordination Note` section if the story's `type` is `new` or `fix`. Missing governance note on new/fix stories → `governance_note_missing` warning (not hard-stop); log and continue.

## Story Queue Resolution

After phase entry passes:

1. Parse `sprint-status.yaml`. Stories are iterable items; each has at minimum `story_id`, `status`, and optionally `blocked_by`.
2. Build the **ready queue**: stories where `status == 'ready'` and all `blocked_by` entries are in the `completed` list of `dev-session.yaml`.
3. If the `epic` input is set, filter the ready queue to stories matching that epic prefix.
4. If the ready queue is empty and there are stories in `status == 'in-progress'` from a prior session: re-enqueue those stories as `ready` (crash recovery).
5. If the ready queue is empty and no stories remain in `ready` or `in-progress`: the sprint is **complete**. Emit `sprint_complete` signal and update `feature.yaml` phase to `dev-complete`.

## Sprint Boundary Pause

After completing every story in the ready queue for the current sprint, emit a `sprint_boundary` pause signal. The conductor MUST wait for explicit user confirmation before advancing to the next sprint. This is not optional and may not be bypassed.

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

1. **Phase entry validation**: Validate feature.yaml phase, sprint-status.yaml, story files, target repo state, and dev-session.yaml integrity.
2. **Story queue resolution**: Build ready queue from sprint-status.yaml and dev-session.yaml completed list.
3. **Branch context**: Confirm or prepare target repo branch via `lens-git-orchestration`.
4. **Story loop**: For each ready story, validate, delegate, test, commit, record, and advance.
5. **Sprint boundary**: Pause after each sprint for user confirmation.
6. **Completion**: When all stories done, emit `sprint_complete`, update feature.yaml to `dev-complete`, prompt user for final PR creation if `requires_final_pr: true`.

## Integration Points

- lens-feature-yaml: read feature state and docs metadata.
- lens-git-state: verify repo/branch status before each story.
- lens-git-orchestration: branch prep and git safety operations.
- lens-bmad-skill: delegated implementation and review actions.
- scripts/dev-session-compat.py: read-time compatibility for old dev-session.yaml formats.
