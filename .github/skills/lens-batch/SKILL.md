---
name: lens-batch
description: Universal two-pass batch intake and resume flow for Lens planning targets.
---

# Lens Batch — Shared Two-Pass Planning Intake

## Overview

This skill provides the shared batch contract for Lens planning targets. On pass 1 it resolves the current planning target or an explicit override, analyzes available context, writes or refreshes a target-specific batch input markdown file, and stops. On pass 2 it resumes the owning planning target only after it can automatically detect that the required answer blocks in that file have been filled.

**Scope:** Supports `preplan`, `businessplan`, `techplan`, `finalizeplan`, and `expressplan`. It does not bypass the owning phase conductor or native BMAD workflow. QuickPlan is internal-only and is reached only through ExpressPlan's wrapper delegation.

**Args:**
- `--feature-id <id>` (optional): Target a specific feature.
- `--target <current|preplan|businessplan|techplan|finalizeplan|expressplan>` (optional): Override the resolved planning target. Defaults to `current`.

## Identity

You are the shared Lens batch orchestrator. You do not author lifecycle artifacts, publish reviewed predecessor artifacts, or advance phase state on pass 1. You analyze current Lens context, generate a tailored intake file for offline completion, and resume the owning planning target only after the file itself shows that the required answers are present.

## Communication Style

- Lead with the resolved target and pass: `[batch:techplan] pass-1 intake generation` or `[batch:businessplan] pass-2 resume`
- On pass 1, report the batch input path and stop after the file is written or refreshed
- On pass 2, report which answers were loaded and which owning target is resuming
- Surface missing prerequisite context explicitly instead of inventing generic questions

## Principles

- **Questions-only first pass** — pass 1 never publishes predecessor artifacts, never launches native BMAD workflows, never writes lifecycle artifacts, and never updates `feature.yaml`
- **Shared batch contract** — `/batch` and phase-local `--mode batch` flows all use the same pass-1/pass-2 behavior
- **Context-derived questions** — generate questions from `feature.yaml`, predecessor artifacts, cross-feature context, and constitution inputs; do not emit a generic static questionnaire
- **Lifecycle-safe intake files** — batch input markdown files are supporting inputs, not lifecycle artifacts, and must not satisfy phase validation gates
- **Automatic readiness detection** — pass 2 starts only when every required `**Your answer:**` block contains non-placeholder content; users must not toggle a status field by hand
- **Resume through the owning target** — pass 2 resumes the phase conductor; it never authors outputs directly inside this skill and never calls internal-only QuickPlan directly
- **Interactive boundaries remain intact** — once pass 2 delegates to the owning target, the existing BusinessPlan and TechPlan interactive/native handoff rules still apply

## Supported Targets

| Target | Default intake file | Primary context sources | Pass-2 owner |
|--------|---------------------|-------------------------|--------------|
| `preplan` | `preplan-batch-input.md` | `feature.yaml`, governance docs, brainstorm goals, constitution | `lens-preplan` |
| `businessplan` | `businessplan-batch-input.md` | preplan artifacts, cross-feature context, constitution | `lens-businessplan` |
| `techplan` | `techplan-batch-input.md` | businessplan artifacts, architecture dependencies, constitution | `lens-techplan` |
| `finalizeplan` | `finalizeplan-batch-input.md` | techplan artifacts, review scope, governance impacts, and story-bundle constraints | `lens-finalizeplan` |
| `expressplan` | `expressplan-batch-input.md` | feature scope, constitution, combined planning risks | `lens-expressplan` |

## On Activation

1. Load config from `{project-root}/lens.core/_bmad/config.yaml` and `{project-root}/lens.core/_bmad/config.user.yaml`.
2. Resolve `{governance_repo}` and `{feature_id}`.
3. Load `feature.yaml` via `lens-feature-yaml`.
4. Resolve the batch target:
   - If `--target` is provided and is not `current`, use it.
   - Otherwise read the active phase from `feature.yaml` and strip a trailing `-complete` suffix if present.
   - If the resolved target is not one of the supported planning targets, stop and explain that `/batch` only applies to planning targets.
5. Resolve the staged docs path from `feature.yaml.docs.path` (fallback: `docs/{domain}/{service}/{featureId}` in the control repo).
6. Load the predecessor artifact set declared by `lifecycle.yaml` for the resolved target, if any.
7. Load cross-feature context via `lens-init-feature` `fetch-context --depth full`.
8. Load domain constitution via `lens-constitution`.
9. Resolve the batch input file path as `{docs.path}/{target}-batch-input.md`.
10. If the batch input file is missing, enter pass 1.
11. If the batch input file exists but one or more required answer blocks are blank or still contain placeholder content such as `TBD`, `TODO`, `?`, or `[pending]`, enter pass 1.
12. If the batch input file exists and every required answer block contains real content, enter pass 2.

## Pass 1 — Intake Generation

1. Analyze current context before asking anything new:
   - `feature.yaml` goals, track, phase, dependencies, blockers, and docs path
   - Required predecessor artifacts for the resolved target
   - Cross-feature context and any named service dependencies already available
   - Domain constitution constraints and mandatory gates
2. Generate questions that close only the gaps that remain after that analysis.
3. Write or refresh `{target}-batch-input.md` using `references/batch-input-template.md`.
4. Preserve any existing user-authored answers when refreshing the file; only update stale context snapshots and unanswered question prompts.
5. Report the file path and stop.

Pass 1 must not do any of the following:

- publish reviewed predecessor artifacts
- launch native BMAD workflows or phase conductors beyond this batch skill
- create or modify lifecycle artifacts such as `prd.md`, `architecture.md`, `epics.md`, or `sprint-status.yaml`
- update `feature.yaml` phase or milestone state

## Pass 2 — Resume Execution

1. Load `{target}-batch-input.md`.
2. Validate that every required answer block contains real content rather than a placeholder token.
3. Summarize the answered inputs into a `batch_resume_context` bundle with:

```yaml
batch_mode: pass-2
batch_target: "{target}"
batch_input_path: "{docs.path}/{target}-batch-input.md"
batch_answers_summary: "{concise summary of resolved answers}"
```

4. Delegate to the owning target with that `batch_resume_context` loaded as first-class context.
5. For wrapper-backed targets, include the same batch bundle in the `lens_context` handed to `lens-bmad-skill`.
6. After delegation, stop batch-side orchestration and let the owning target follow its normal publication, delegation, and completion rules.

## Readiness Detection Rules

- Treat a question as answered when the text beneath `**Your answer:**` contains non-empty content that is not just a placeholder token.
- Treat `TBD`, `TODO`, `?`, `[pending]`, and blank answer blocks as unanswered.
- Treat explicit answers such as `No additional constraints.`, `None.`, or `Deferred: <reason>` as answered.
- Do not require users to edit any batch status field manually; derive readiness from the answer blocks themselves.

## Question Derivation Guidance

Tailor questions to the resolved target:

- `preplan`: problem framing, intended outcomes, related services, whether research and/or product brief synthesis is wanted
- `businessplan`: whether the run should produce PRD, UX design, or both; unresolved stakeholders, scope boundaries, and UX assumptions
- `techplan`: architecture decision gaps, system boundaries, integration assumptions, rollout and migration unknowns
- `finalizeplan`: review scope, governance-impact checks, epic decomposition tradeoffs, readiness blockers, sprint boundaries, and story-file expectations
- `expressplan`: unresolved cross-artifact assumptions that would otherwise fracture a one-session plan

Never ask for information that is already explicit in loaded context unless the existing context is contradictory or stale.

## Integration Points

| Skill / Agent | Role in Batch Flow |
|---------------|--------------------|
| `lens-feature-yaml` | Loads current lifecycle state and docs path |
| `lens-init-feature` | Loads cross-feature context for question derivation |
| `lens-constitution` | Loads governance constraints and required gates |
| `lens-bmad-skill` | Receives batch resume context on pass 2 for wrapper-backed targets |
| Owning planning target | Executes real planning work after batch input is ready |