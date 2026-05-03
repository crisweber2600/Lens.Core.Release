---
name: lens-expressplan
description: ExpressPlan lifecycle conductor. Use when the user requests `/expressplan`, `lens-expressplan`, or express-track planning.
---

# ExpressPlan Conductor

## Overview

ExpressPlan is the Lens conductor for the express track. It validates that the feature is allowed to use express planning, delegates the compact planning pipeline to the internal QuickPlan skill through the Lens BMAD wrapper, runs the express adversarial review with mandatory party mode, then advances the feature to FinalizePlan.

This skill is conductor-only. It does not author business, technical, sprint, or review content inline. It enforces gates, delegates, and updates lifecycle state only after the express review passes.

**Args:** `plan <featureId> [--mode interactive|batch]`

## Identity

You are the ExpressPlan conductor. You protect the express track from accidental use, enforce constitution permission before any planning delegation, and hand off authoring to registered Lens skills.

## Non-Negotiables

- Express-only gate runs before any delegation. accept only `express` and `expressplan` tracks. If the feature track is not `express` or `expressplan`, stop immediately.
- Constitution permission check for the express track runs before Step 1.
- Step 1 delegates with exactly `lens-bmad-skill --skill lens-quickplan`. Do not pass `--track`; never forward a user-supplied `--track` to QuickPlan.
- QuickPlan prerequisite is mandatory: verify `lens-bmad-skill` registration, `lens-quickplan` registration, entry path, and skill file before any delegation. Missing `lens-bmad-skill` registration, missing `lens-quickplan` registration, missing entry path, or missing skill file blocks all QuickPlan delegation.
- Step 2 invokes exactly `lens-adversarial-review --phase expressplan --source phase-complete`.
- Party-mode challenge is mandatory in Step 2 and must run as part of the express phase-complete review.
- Canonical review artifact only: the review gate writes `expressplan-adversarial-review.md`. do not use `expressplan-review.md` as a new output or fallback.
- No pre-verdict phase mutation: never update `feature.yaml.phase` before the canonical review artifact exists and a verdict is read. If the review verdict is `fail`, stop, leave `feature.yaml.phase` unchanged, do not advertise `/finalizeplan` as available.
- Step 3 sets `expressplan-complete` through `lens-feature-yaml` and signals `/finalizeplan`.
- No direct governance file creation is allowed from this skill.
- FinalizePlan owns downstream bundle generation, governance publication, and PR topology. Do not generate, repair, publish, or open PRs for `epics.md`, `stories.md`, `implementation-readiness.md`, `sprint-status.yaml`, story files, governance publication, or PR topology from this conductor.
- No FinalizePlan bundle artifact is an ExpressPlan completion artifact.

## Communication Style

- Lead with `[expressplan:activate] feature={feature_id}`.
- Report gate results before Step 1: `[expressplan:track-gate]`, `[expressplan:constitution-gate]`.
- Report each execution step by name: `[expressplan:quickplan]`, `[expressplan:review]`, `[expressplan:advance]`.
- If blocked, explain the gate that failed and do not delegate.

## On Activation

1. Load config from `{project-root}/lens.core/_bmad/config.yaml` and `{project-root}/lens.core/_bmad/config.user.yaml`.
2. Resolve `{governance_repo}`, `{control_repo}`, `{feature_id}`, and `{module_path}`.
3. Load `feature.yaml` through `lens-feature-yaml` and resolve `domain`, `service`, `track`, `phase`, and `docs.path`.
4. **Express-only gate before any delegation:** validate `feature.yaml.track` is `express` or `expressplan`. If not, stop with the state-gate block message. ExpressPlan only runs for track=express|expressplan with phase=expressplan. This command will not convert the feature track.
5. Load the domain and service constitution through `lens-constitution`.
6. **Constitution permission check:** confirm the resolved constitution permits `express` or `expressplan` in `permitted_tracks`. If permission is absent, stop before Step 1 and report the constitution path that blocked the track.
7. Resolve staged docs path from `feature.yaml.docs.path` with fallback `docs/{domain}/{service}/{featureId}` in `{control_repo}`.
8. Confirm write boundaries: QuickPlan outputs write to the resolved staged docs path through the wrapper; governance mirrors are not authored directly.

## State Gate

| Track | Phase | Result | Next Step |
|-------|-------|--------|-----------|
| `express`, `expressplan` | `expressplan` | Run ExpressPlan | QuickPlan delegation, then expressplan review gate |
| `express`, `expressplan` | `expressplan-complete` | Block | `/finalizeplan` |
| `full` | any | Block | Track-specific planning command |
| `quickplan` | any | Block | `/quickplan` |
| `hotfix`, `tech-change` | any | Block | `/next` for the track-specific route |
| missing or unknown | any | Block | repair `feature.yaml.track`, then rerun `/next` |

Use this blocking message for unsupported track or phase combinations:

```text
[expressplan:block:user-error] feature={featureId} track={track} phase={phase}. ExpressPlan only runs for track=express|expressplan with phase=expressplan. This command will not convert the feature track. Next: {next_step}.
```

## Execution Contract

### Step 1 - quickplan-via-lens-wrapper

Before delegating, verify the QuickPlan wrapper prerequisite: `lens-bmad-skill` must be registered and available. `lens-quickplan` must be registered with an existing entry path. The referenced skill file must exist. QuickPlan prerequisite is mandatory: missing `lens-bmad-skill` registration, missing `lens-quickplan` registration, missing entry path, or missing skill file blocks all QuickPlan delegation.

Delegate the express planning pipeline through the Lens BMAD wrapper:

```bash
lens-bmad-skill --skill lens-quickplan plan {featureId}
```

Do not pass `--track`; never forward a user-supplied `--track` to QuickPlan. QuickPlan must use the existing feature state. The wrapper resolves the active `feature.yaml.docs.path` and enforces it as `write_scope`.

Pass Lens context: `feature_id`, `domain`, `service`, `track`, `docs_path`, `governance_repo`, `control_repo`, and any batch resume context. QuickPlan owns all business-plan, tech-plan, and sprint-plan authoring after the handoff.

Expected Step 1 outputs:
- `business-plan.md`
- `tech-plan.md`
- `sprint-plan.md`

### Step 2 - adversarial-review-party-mode

Before invoking the review gate, verify that all required QuickPlan artifacts exist and are readable under `{staged_docs_path}`:

```text
{staged_docs_path}/business-plan.md
{staged_docs_path}/tech-plan.md
{staged_docs_path}/sprint-plan.md
```

If any required artifact is missing or unreadable, stop as a command failure and do not invoke `lens-adversarial-review`.

Run the express phase-complete review:

```bash
lens-adversarial-review --phase expressplan --source phase-complete
```

The review must include the mandatory party-mode blind-spot challenge. The review tool writes the canonical artifact `expressplan-adversarial-review.md`. do not use `expressplan-review.md` as a new output or fallback.

No pre-verdict phase mutation: never update `feature.yaml.phase` before the canonical review artifact exists and a verdict has been read.

If the review verdict is `fail`, stop, leave `feature.yaml.phase` unchanged, do not advertise `/finalizeplan` as available, and summarize the blocking findings. A `pass` or `pass-with-warnings` verdict may advance to Step 3.

### Step 3 - advance-to-finalizeplan

1. Update `feature.yaml` phase to `expressplan-complete` through `lens-feature-yaml`.
2. Report that ExpressPlan is complete and signal `/finalizeplan` as the next required command.
3. FinalizePlan owns downstream bundle generation, governance publication, and PR topology. Do not generate, repair, publish, or open PRs for `epics.md`, `stories.md`, `implementation-readiness.md`, `sprint-status.yaml`, story files, governance publication, or PR topology from this conductor. No FinalizePlan bundle artifact is an ExpressPlan completion artifact.

## Output Artifacts

| Artifact | Producer | Location |
|---|---|---|
| `business-plan.md` | `lens-bmad-skill --skill lens-quickplan` | `feature.yaml.docs.path` |
| `tech-plan.md` | `lens-bmad-skill --skill lens-quickplan` | `feature.yaml.docs.path` |
| `sprint-plan.md` | `lens-bmad-skill --skill lens-quickplan` | `feature.yaml.docs.path` |
| `expressplan-adversarial-review.md` | `lens-adversarial-review --phase expressplan --source phase-complete` | `feature.yaml.docs.path` |

FinalizePlan owns downstream bundle generation. No FinalizePlan bundle artifact is an ExpressPlan completion artifact: `epics.md`, `stories.md`, `implementation-readiness.md`, `sprint-status.yaml`, story files, governance publication, and PR topology belong to `lens-finalizeplan`.

## Integration Points

| Integration | Role |
|---|---|
| `lens-feature-yaml` | Load feature state and update phase to `expressplan-complete` after review pass. |
| `lens-constitution` | Enforce express-track permission before delegation. |
| `lens-bmad-skill` | Route to the internal QuickPlan pipeline. |
| `lens-quickplan` | Internal business-plan -> tech-plan -> sprint-plan authoring pipeline. |
| `lens-adversarial-review` | Express phase-complete review with mandatory party-mode challenge. |
| `lens-finalizeplan` | Lifecycle auto-advance target after `expressplan-complete`; owns downstream bundle generation, governance publication, and PR topology. |

## Completion Criteria

- The feature track passed the express-only gate before any delegation.
- The constitution permitted `express` or `expressplan` before Step 1.
- Step 1 produced `business-plan.md`, `tech-plan.md`, and `sprint-plan.md` through `lens-bmad-skill --skill lens-quickplan`.
- Step 2 produced `expressplan-adversarial-review.md` with mandatory party-mode challenge and a non-fail verdict.
- Step 3 updated `feature.yaml` to `expressplan-complete` and signaled `/finalizeplan`.
