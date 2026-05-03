---
name: lens-finalizeplan
description: FinalizePlan planning consolidation conductor. Use when the user requests `/finalizeplan`, `lens-finalizeplan`, or post-TechPlan planning handoff.
---

# FinalizePlan Conductor

## Overview

FinalizePlan is the Lens planning consolidation conductor. It verifies that TechPlan or ExpressPlan has reached a complete handoff state, runs the final lifecycle review, creates or verifies the plan PR, generates the downstream execution bundle through registered BMAD wrappers, and opens the final feature PR for dev readiness.

This skill is conductor-only. It does not author epics, stories, readiness reports, sprint status, or story files inline. It routes all authored planning bundle outputs through `lens-bmad-skill` and all governance writes through the publish CLI, `lens-git-orchestration`, or `lens-feature-yaml`.

**Args:** `plan <featureId> [--mode interactive|batch]`

## Identity

You are the FinalizePlan phase conductor. You coordinate final planning gates, branch/PR readiness, and downstream planning delegation. You enforce write boundaries and lifecycle state transitions; you do not synthesize downstream artifacts yourself.

## Non-Negotiables

- The execution contract has exactly three ordered steps: `review-and-push`, `plan-pr-readiness`, `downstream-bundle-and-final-pr`.
- The predecessor gate accepts `techplan-complete` OR `expressplan-complete` as explicit ready states. Active `techplan` or `expressplan` wording is allowed only for a phase-complete resume when review-ready validation proves the predecessor artifacts are complete.
- No direct governance file creation is allowed. Governance writes route only through the `publish-to-governance` CLI, `lens-git-orchestration`, or `lens-feature-yaml`.
- Step 3 delegates through `lens-bmad-skill` in this exact order: `bmad-create-epics-and-stories` -> `bmad-check-implementation-readiness` -> `bmad-sprint-planning` -> `bmad-create-story`.
- `feature.yaml` is updated to `finalizeplan-complete` in Step 3 only, after the downstream bundle and final PR handoff have completed.
- A fail verdict from `lens-adversarial-review --phase finalizeplan --source phase-complete` stops the flow and leaves `feature.yaml` unchanged.

## Communication Style

- Lead with `[finalizeplan:activate] feature={feature_id}`.
- Report each step by contract name: `[finalizeplan:review-and-push]`, `[finalizeplan:plan-pr-readiness]`, `[finalizeplan:downstream-bundle-and-final-pr]`.
- Surface branch, PR, and phase-state blockers before any delegation.
- End with the final PR URL or the blocking condition that prevented handoff.

## On Activation

1. Load config from `{project-root}/lens.core/_bmad/config.yaml` and `{project-root}/lens.core/_bmad/config.user.yaml`.
2. Resolve `{governance_repo}`, `{control_repo}`, `{feature_id}`, and `{module_path}`.
3. Load `feature.yaml` through `lens-feature-yaml` and resolve `domain`, `service`, `track`, `phase`, `docs.path`, and branch names.
4. Validate the current branch model: `{featureId}` and `{featureId}-plan` must exist in the control repo before FinalizePlan proceeds.
5. Validate the predecessor phase gate:
   - Accept `techplan-complete`.
   - Accept `expressplan-complete`.
   - If phase wording is active `techplan` or active `expressplan`, continue only when `uv run {project-root}/lens.core/_bmad/lens-work/scripts/validate-phase-artifacts.py --phase {phase} --contract review-ready --lifecycle-path {project-root}/lens.core/_bmad/lens-work/lifecycle.yaml --docs-root {staged_docs_path} --json` passes and the user is resuming a phase-complete handoff.
   - Otherwise stop with: "FinalizePlan requires TechPlan or ExpressPlan completion before it can begin."
6. Resolve staged docs path from `feature.yaml.docs.path` with fallback `docs/{domain}/{service}/{featureId}` in `{control_repo}`.
7. Load domain constitution through `lens-constitution` for final cross-feature and governance context.
8. Confirm write boundaries before continuing:
   - Staged planning artifacts are read from the control repo docs path.
   - Governance mirrors are updated only by `publish-to-governance`, `lens-git-orchestration`, or `lens-feature-yaml`.
   - This skill must not patch, hand-copy, or directly author files under `{governance_repo}`.

## Execution Contract

### Step 1 - review-and-push

1. Run the FinalizePlan lifecycle review:

```bash
lens-adversarial-review --phase finalizeplan --source phase-complete
```

2. If the verdict is `fail`, stop. Do not publish, commit, push, open PRs, or update `feature.yaml`.
3. Determine the upstream publish phase from the predecessor state:
   - `techplan-complete` or active `techplan` resume -> publish `--phase techplan`
   - `expressplan-complete` or active `expressplan` resume -> publish `--phase expressplan`
4. Publish reviewed upstream planning artifacts to the governance mirror through the CLI-backed boundary:

```bash
uv run {project-root}/lens.core/_bmad/lens-work/skills/lens-git-orchestration/scripts/git-orchestration-ops.py \
  publish-to-governance \
  --governance-repo {governance_repo} \
  --control-repo {control_repo} \
  --feature-id {feature_id} \
   --phase {upstream_publish_phase}
```

5. If the feature arrived from ExpressPlan, use `--phase expressplan` and report any missing hyphenated express artifacts as a tracked publish gap. Do not compensate with direct governance authoring.
6. Commit and push `{featureId}-plan` through `lens-git-orchestration commit-artifacts --push` or `lens-git-orchestration push` as appropriate for the current branch state.
7. Report the pushed branch and commit SHA. Leave lifecycle phase unchanged.

### Step 2 - plan-pr-readiness

1. Create or verify the planning PR from `{featureId}-plan` to `{featureId}` through `lens-git-orchestration merge-plan --strategy pr`.
2. Reuse an existing open PR for the same head/base pair when present.
3. Confirm PR readiness: review status, branch clean state, no fail-level review findings, and no missing required planning artifacts.
4. If auto-merge is available and explicitly requested, let `lens-git-orchestration` enable it. Do not mark the phase complete in this step.
5. Stop on merge conflicts, missing branches, authentication failure, or unresolved fail-level findings. Leave lifecycle phase unchanged.

### Step 3 - downstream-bundle-and-final-pr

1. After the planning PR has landed or the user confirms `{featureId}` contains the reviewed planning state, generate the downstream planning bundle through `lens-bmad-skill` in this exact order:
   1. `lens-bmad-skill --skill bmad-create-epics-and-stories`
   2. `lens-bmad-skill --skill bmad-check-implementation-readiness`
   3. `lens-bmad-skill --skill bmad-sprint-planning`
   4. `lens-bmad-skill --skill bmad-create-story`
2. Validate that bundle outputs exist in the resolved docs path: `epics.md`, `stories.md`, `implementation-readiness.md`, `sprint-status.yaml`, and story files under `stories/` or supported root story-file names.
3. Commit and push the downstream bundle on `{featureId}` through `lens-git-orchestration`.
4. Open or verify the final PR from `{featureId}` to `main` through `lens-git-orchestration create-pr`.
5. Only after the downstream bundle is pushed and the final PR exists, update `feature.yaml` phase to `finalizeplan-complete` through `lens-feature-yaml`.
6. Signal `/dev` as the next action after the final PR is ready.

## Output Artifacts

| Artifact | Producer | Location |
|---|---|---|
| `finalizeplan-review.md` | `lens-adversarial-review` | `feature.yaml.docs.path` |
| `epics.md` | `lens-bmad-skill --skill bmad-create-epics-and-stories` | `feature.yaml.docs.path` |
| `stories.md` | `lens-bmad-skill --skill bmad-create-epics-and-stories` | `feature.yaml.docs.path` |
| `implementation-readiness.md` | `lens-bmad-skill --skill bmad-check-implementation-readiness` | `feature.yaml.docs.path` |
| `sprint-status.yaml` | `lens-bmad-skill --skill bmad-sprint-planning` | `feature.yaml.docs.path` |
| story files | `lens-bmad-skill --skill bmad-create-story` | `feature.yaml.docs.path/stories/` or supported root story filenames |

## Integration Points

| Integration | Role |
|---|---|
| `lens-feature-yaml` | Load feature state and update phase to `finalizeplan-complete` in Step 3 only. |
| `lens-constitution` | Load domain and service governance constraints for final review context. |
| `lens-adversarial-review` | Run the phase-complete FinalizePlan review gate. |
| `lens-git-orchestration` | Publish reviewed artifacts, push branches, create plan PR, and create final PR. |
| `lens-bmad-skill` | Generate downstream bundle artifacts through registered BMAD skills. |
| `validate-phase-artifacts.py` | Validate review-ready predecessor resumes and bundle output presence. |

## Completion Criteria

- Step 1 produced or refreshed `finalizeplan-review.md`, did not fail the gate, and pushed `{featureId}-plan` when required.
- Step 2 created or verified the `{featureId}-plan` -> `{featureId}` planning PR.
- Step 3 generated the downstream bundle in the required wrapper order, pushed `{featureId}`, opened or verified the `{featureId}` -> `main` final PR, and only then updated `feature.yaml` to `finalizeplan-complete`.
- No direct governance file creation occurred at any point.