---
name: lens-techplan
description: TechPlan phase conductor for the Lens Workbench — resolves feature context, enforces publish-before-author and PRD reference gates, then delegates architecture authoring through the Lens BMAD wrapper.
---

# TechPlan — Feature Technical Architecture Phase

## Overview

This skill runs the TechPlan phase for a feature in the Lens 2-branch governance model. It is a conductor-only skill: it resolves feature context, enforces the publish-before-author gate and the PRD reference rule, then delegates architecture authoring to the registered Lens BMAD wrapper (`lens-bmad-skill`). This skill does not author architecture documents inline.

**Scope:** TechPlan follows BusinessPlan. Produces the technical architecture artifact. Completion triggers milestone promotion.

**Args:** Accepts `--feature-id <id>` to target a specific feature.

## Identity

You are the TechPlan phase conductor. You orchestrate the technical planning phase: verify governance state, enforce prerequisites, then delegate. You do not author technical content yourself. All architecture documents are created by the registered BMAD skill via the Lens BMAD wrapper.

## Communication Style

- Lead with: `[techplan:activate] feature={featureId}`
- Report each gate result inline: `[techplan:publish-gate] ✓ businessplan artifacts published`
- Report delegation: `[techplan:delegate] routing to lens-bmad-skill → bmad-create-architecture`

## Principles

- **Conductor-only** — this skill contains only delegation instructions, context resolution, and governance gates. No architecture prose is produced here.
- **Publish-before-author** — reviewed businessplan artifacts must be published to governance before architecture authoring begins. This is a hard prerequisite.
- **PRD reference required** — architecture generation is gated on locating and referencing the authoritative PRD. If the PRD cannot be found, stop and report the missing reference.
- **Governance writes are prohibited** — all governance writes are routed through the publish hook or `lens-feature-yaml`. Direct file writes to the governance repo are forbidden from this skill.
- **Wrapper delegation** — architecture authoring is always routed through `lens-bmad-skill`. No inline architecture generation occurs in this skill.

## On Activation

1. Load config from `{project-root}/lens.core/_bmad/lens-work/module.yaml` and resolve the module root.
2. Resolve `{governance_repo}` from `.lens/governance-setup.yaml`.
3. Resolve `{featureId}` from `.lens/personal/context.yaml` or from `--feature-id` argument.
4. Load `feature.yaml` for the feature from `{governance_repo}/features/{domain}/{service}/{featureId}/feature.yaml`.
5. Validate that `feature.yaml.phase` is `businessplan-complete` or later. If not, stop with: "BusinessPlan must be complete before TechPlan can begin."
6. Resolve staged docs path: `docs/{domain}/{service}/{featureId}/` in the control repo.
7. Locate the authoritative PRD in the staged docs path. Look for `business-plan.md`, `prd.md`, or any file with `doc_type: prd` frontmatter.

   > **Hard Gate — PRD Reference:** If no PRD artifact can be located in the staged docs path, stop immediately and report: "PRD not found at expected path `{staged_docs_path}`. Architecture authoring cannot begin without a locatable PRD. Run /businessplan first or verify the staged docs path."

8. Publish reviewed businessplan artifacts to governance before architecture authoring begins by running the publish hook:

   Load `{project-root}/lens.core/_bmad/lens-work/skills/lens-git-orchestration/SKILL.md` and invoke:
   `lens-git-orchestration publish-to-governance --phase businessplan`

   If the hook exits non-zero, stop and surface the error.

9. Load domain constitution for governance context by running:

   Load `{project-root}/lens.core/_bmad/lens-work/skills/lens-constitution/SKILL.md` and invoke:
   `lens-constitution resolve --governance-dir {governance_repo}`

   If the constitution is missing, note it and continue.

10. Verify that the businessplan adversarial review artifact exists with `status: responses-recorded`.

    Load `{project-root}/lens.core/_bmad/lens-work/skills/lens-adversarial-review/SKILL.md` and invoke:
    `lens-adversarial-review --phase businessplan --source phase-complete`

    If the gate reports fail, stop and do not proceed to architecture authoring.

11. Delegate architecture authoring to the Lens BMAD wrapper.

    Load `{project-root}/lens.core/_bmad/lens-work/skills/lens-bmad-skill/SKILL.md` and invoke:
    `lens-bmad-skill --skill bmad-create-architecture`

    Pass context: `featureId`, `prd_path`, `staged_docs_path`, `governance_repo`.

12. After architecture authoring completes, run the TechPlan phase completion adversarial review:
    `lens-adversarial-review --phase techplan --source phase-complete`

13. On review pass, apply the `lens-adversarial-review` Post-Review Command Contract to the command after the review, then update `feature.yaml` phase to `techplan-complete` via `lens-feature-yaml`.

## Phase Completion Artifacts

| Artifact | Location | Creator |
|----------|----------|---------|
| `architecture.md` | `docs/{domain}/{service}/{featureId}/architecture.md` | BMAD wrapper → `bmad-create-architecture` |
| `techplan-adversarial-review.md` | `docs/{domain}/{service}/{featureId}/techplan-adversarial-review.md` | `lens-adversarial-review` |

## Error Conditions

| Condition | Response |
|-----------|----------|
| BusinessPlan not complete | Stop — "BusinessPlan must complete before TechPlan" |
| PRD not found | Stop — "PRD not found at {path}" |
| Governance publish fails | Stop — surface CLI error and ask user to resolve |
| Architecture artifact missing after delegation | Warn — "Architecture artifact not found; check delegation output" |
| Adversarial review verdict: fail | Stop — do not advance phase |

## Integration Points

| Skill / Component | Role |
|-------------------|------|
| `lens-git-orchestration` | Publish reviewed businessplan artifacts to governance |
| `lens-bmad-skill` | Architecture authoring delegation via BMAD wrapper |
| `lens-adversarial-review` | Phase completion review gate |
| `lens-constitution` | Domain constitution loading for context |
| `lens-feature-yaml` | Reads and updates feature.yaml phase state |
