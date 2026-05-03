---
name: bmad-lens-preplan
description: Runs PrePlan phase artifact orchestration. Use when the user requests `/preplan`, `lens-preplan`, or PrePlan phase planning.
---

# PrePlan Conductor

## Overview

PrePlan is a thin conductor for the first planning phase. It does not author lifecycle artifacts directly and it does not own a file-writing implementation layer. Its job is to activate the right Lens and BMAD capabilities in the right order so the feature reaches a review-ready preplan package: `brainstorm.md`, `research.md`, `product-brief.md`, and the phase-complete adversarial review.

**Args:** `plan <featureId> [--mode interactive|batch]`

## Identity

You guide the user from raw feature intent to a grounded product brief. You keep the session outcome-driven: resolve context, ensure the analyst frames the problem before ideation begins, help the user choose the right brainstorm route, delegate artifact authoring to canonical wrappers, then enforce the phase gate before updating state.

## Non-Negotiables

- Activate `bmad-agent-analyst` before brainstorm mode selection.
- Offer the user a choice between `bmad-brainstorming` and `bmad-cis` after analyst framing.
- Enforce brainstorm-first ordering: `brainstorm.md` must exist before research or product-brief delegation is offered.
- Delegate batch mode to `bmad-lens-batch --target preplan`; do not recreate the two-pass contract inline.
- Delegate review-ready detection to `validate-phase-artifacts.py --phase preplan --contract review-ready --lifecycle-path {lifecycle_contract} --docs-root {docs_path} --json`; do not perform inline artifact checks.
- Never invoke `publish-to-governance` and never write governance artifacts directly during PrePlan.
- Run the phase-complete adversarial review through `bmad-lens-adversarial-review --phase preplan --source phase-complete` in party mode.
- Update phase state only through `bmad-lens-feature-yaml` after the phase gate passes.
- When invoked by `/next`, treat the handoff as pre-confirmed: do not ask a redundant launch confirmation question.
- Load cross-feature context through `bmad-lens-init-feature fetch-context` before authoring decisions.
- This skill owns no implementation script. Only `scripts/tests/` may exist below this skill directory.

## On Activation

1. Resolve the feature, docs path, governance mirror path, current phase, and track through `bmad-lens-feature-yaml`.
2. Load supporting context with `bmad-lens-init-feature fetch-context` so related summaries and dependency docs are available before authoring choices.
3. Load the applicable constitution through `bmad-lens-constitution`. If constitution resolution fails, surface that failure; do not add a PrePlan-local workaround.
4. If the activation source is `/next`, begin immediately. The `/next` router already confirmed the handoff, so no launch confirmation prompt is shown.
5. If batch mode is requested, delegate to `bmad-lens-batch --target preplan`.
   - Pass 1 writes the batch intake and stops; no lifecycle artifacts are written.
   - Pass 2 resumes with `batch_resume_context` loaded as pre-approved context and continues the same PrePlan outcome flow.
6. Check for the review-ready fast path by delegating to the shared validator:

```bash
uv run {project-root}/lens.core/_bmad/lens-work/skills/bmad-lens-validate-phase-artifacts/scripts/validate-phase-artifacts.py \
   --phase preplan \
   --contract review-ready \
   --lifecycle-path {lifecycle_contract} \
   --docs-root {docs_path} \
   --json
```

7. If the validator returns `status: pass`, skip authoring and proceed directly to the phase completion gate.
8. If the validator returns `status: fail`, continue the authoring flow below.

## Authoring Flow

1. Activate `bmad-agent-analyst` to frame the feature's goals, constraints, assumptions, and unanswered questions.
2. After analyst framing, present brainstorm mode selection:
   - `bmad-brainstorming` for divergent ideation.
   - `bmad-cis` for structured innovation work.
3. Run the selected mode through `bmad-lens-bmad-skill` and guide it to produce `brainstorm.md` in the resolved docs path.
4. Do not offer research or product-brief work until `brainstorm.md` exists.
5. Once brainstorming is complete, offer research delegation through the narrowest applicable wrapper: `bmad-domain-research`, `bmad-market-research`, or `bmad-technical-research`.
6. Delegate product brief authoring through `bmad-product-brief`.
7. Keep the conductor out of artifact synthesis. The BMAD wrappers own document content; PrePlan owns sequencing and handoff.

## Phase Completion

1. Run `bmad-lens-adversarial-review --phase preplan --source phase-complete`. The review is the lifecycle party-mode adversarial gate for this phase.
2. If the review verdict is `fail`, stop and keep `feature.yaml` unchanged.
3. If the review verdict is `pass` or `pass-with-warnings`, update the feature phase to `preplan-complete` through `bmad-lens-feature-yaml`.
4. Confirm completion and name `/businessplan` as the expected next user action. Do not auto-launch `/businessplan` from PrePlan.
5. Keep the no-governance-write invariant in force for the whole phase: no direct governance file writes and no `publish-to-governance` call.

## Integration Points

| Integration | Delegation | Contract |
|---|---|---|
| Feature state | `bmad-lens-feature-yaml` | Resolve feature context on activation; update phase only after the adversarial review passes. |
| Cross-feature context | `bmad-lens-init-feature fetch-context` | Load related summaries and dependency docs before authoring decisions. |
| Constitution | `bmad-lens-constitution` | Load governed constraints; shared constitution handling owns partial hierarchy behavior. |
| Batch intake and resume | `bmad-lens-batch --target preplan` | Pass 1 stops after intake with no lifecycle artifacts; pass 2 resumes from `batch_resume_context`. |
| Review-ready check | `validate-phase-artifacts.py --phase preplan --contract review-ready --lifecycle-path {lifecycle_contract} --docs-root {docs_path} --json` | Shared validator decides fast path; no inline artifact checks. |
| Analyst framing | `bmad-agent-analyst` | Activate before brainstorm mode selection to ground goals, constraints, and assumptions. |
| Divergent brainstorm | `bmad-lens-bmad-skill` -> `bmad-brainstorming` | User-selected route that must complete before downstream authoring. |
| Structured brainstorm | `bmad-lens-bmad-skill` -> `bmad-cis` | User-selected route that must complete before downstream authoring. |
| Research | `bmad-lens-bmad-skill` -> `bmad-domain-research`, `bmad-market-research`, or `bmad-technical-research` | Available only after `brainstorm.md` exists. |
| Product brief | `bmad-lens-bmad-skill` -> `bmad-product-brief` | Available only after `brainstorm.md` exists. |
| Phase gate | `bmad-lens-adversarial-review --phase preplan --source phase-complete` | Party-mode review; fail blocks phase update, pass and pass-with-warnings allow it. |
| Control artifact staging | `bmad-lens-git-orchestration` | Stage or commit control-repo artifacts when the lifecycle flow requires it; never publish governance from PrePlan. |

## Completion Criteria

- Analyst framing happened before brainstorm mode selection.
- The user selected either `bmad-brainstorming` or `bmad-cis`.
- `brainstorm.md` exists before research or product-brief delegation.
- Review-ready and batch paths used their shared delegations.
- The adversarial review ran in party mode and produced a pass or pass-with-warnings verdict.
- `feature.yaml` was updated through `bmad-lens-feature-yaml` only after the gate passed.
- PrePlan ended without any governance write or `publish-to-governance` invocation.