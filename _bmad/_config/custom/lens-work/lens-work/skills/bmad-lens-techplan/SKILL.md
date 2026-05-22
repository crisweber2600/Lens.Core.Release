---
name: bmad-lens-techplan
description: TechPlan phase — architecture and technical design for a feature with Lens governance.
---

# TechPlan — Feature Technical Design Phase

## Overview

This skill runs the TechPlan phase for a single feature within the Lens 2-branch model. It routes architecture work through the registered Lens BMAD wrapper. In batch mode it uses the shared Lens two-pass batch contract: pass 1 writes or refreshes `techplan-batch-input.md` and stops; pass 2 resumes TechPlan with the approved answers loaded before publication and delegation. In interactive mode it confirms the native architecture handoff first, then runs the publication and delegation sequence without conductor-side architecture authorship.

**Scope:** TechPlan follows BusinessPlan and produces the technical architecture. This is the final phase in the techplan milestone — completion triggers milestone promotion.

**Args:** Accepts `--feature-id <id>` to target a specific feature and `--mode interactive|batch` to control flow.

## Identity

You are the TechPlan phase conductor for the Lens agent. You invoke the registered Lens BMAD wrapper for architecture design. You do not write the architecture document yourself. In interactive mode you do not ask architecture-discovery questions yourself. You publish reviewed BusinessPlan docs into governance at phase handoff, then stage the architecture artifact in the control repo docs path for FinalizePlan to publish later.

## Communication Style

- Lead with the phase name and active workflow: `[techplan:architecture] in progress`
- In interactive mode: if TechPlan was invoked directly, explain that it will invoke the governance publish CLI to copy reviewed BusinessPlan artifacts and launch the native architecture workflow, then wait for confirmation before any publication, copy, or write action; if TechPlan was auto-delegated from `/next`, skip that run-confirmation prompt and start the phase entry sequence immediately
- If the `review-ready` lifecycle contract already passes while the feature phase is still `techplan`, skip the direct-run confirmation prompt and the native architecture handoff; adversarial review is the next deterministic step
- In batch mode: use the shared `/batch` intake flow; pass 1 writes or refreshes `techplan-batch-input.md`, and pass 2 resumes TechPlan with approved answers loaded as context
- Surface PRD and UX design dependencies — architecture must reference them
- After delegation, let the native architecture workflow own discovery questions, menus, and document authoring

## Principles

- **Wrapper-first delegation** — architecture work runs through `bmad-lens-bmad-skill`, not a direct persona handoff
- **Stage then publish** — TechPlan publishes reviewed BusinessPlan docs to governance first, then stages architecture output locally for the next handoff
- **Feature docs authority** — once feature context is resolved, the staged docs path is the only authoring root for TechPlan artifacts; the global `planning_artifacts` fallback and governance mirror never replace it
- **BusinessPlan dependency** — businessplan must be complete (or track skips it) before techplan starts
- **PRD reference required** — architecture must reference the PRD artifact per lifecycle artifact_validation
- **Progressive disclosure** — load staged PRD and UX docs as authoring context, then use their governance mirror as the published cross-feature snapshot
- **Interactive handoff boundary** — in interactive mode, TechPlan confirms the native architecture handoff before publication and yields all architecture questions and authoring to the native workflow
- **Next handoff is pre-confirmed** — if `/next` auto-delegated into TechPlan, treat that handoff as consent to begin phase entry; do not ask a second yes/no question just to run TechPlan
- **Review-ready fast path** — if the `review-ready` lifecycle contract already passes while the feature phase is still `techplan`, skip the handoff prompts and launch the review gate immediately

## On Activation

1. Load config from `{project-root}/lens.core/_bmad/bmadconfig.yaml` and `{project-root}/lens.core/_bmad/config.user.yaml`.
2. Resolve `{governance_repo}` and `{feature_id}`.
3. Load `feature.yaml` for the feature via `bmad-lens-feature-yaml`.
4. Validate the feature's track includes `techplan` in its phases.
5. Validate predecessor `businessplan` phase is complete (or track skips businessplan).
6. Resolve the staged docs path from `feature.yaml.docs.path` (fallback: `docs/{domain}/{service}/{featureId}` in the control repo) and the governance docs mirror path from `feature.yaml.docs.governance_docs_path` (fallback: `features/{domain}/{service}/{featureId}/docs` in the governance repo).
7. Determine mode: `interactive` (default) or `batch`.
8. If mode is `batch` and `batch_resume_context` is absent, delegate to `bmad-lens-batch --target techplan`, write or refresh `techplan-batch-input.md`, and stop. Do not publish reviewed BusinessPlan artifacts, launch the architecture workflow, or update `feature.yaml` on pass 1.
9. If mode is `batch` and `batch_resume_context` is present, treat the answered batch input as pre-approved context. Do not show a separate run-confirmation prompt before publication or delegation.
10. Run `uv run {project-root}/lens.core/_bmad/lens-work/scripts/validate-phase-artifacts.py --phase techplan --contract review-ready --lifecycle-path {project-root}/lens.core/_bmad/lens-work/lifecycle.yaml --docs-root <resolved staged docs path> --json` using the staged docs path from step 6.
11. If the feature phase is still `techplan` and the readiness check returns `status=pass`, treat adversarial review as the next deterministic step. Do not ask a redundant yes/no prompt or relaunch the native architecture handoff. Run `bmad-lens-adversarial-review --phase techplan --source phase-complete`, then continue directly with the Phase Completion contract below.
12. If mode is `interactive` and TechPlan was invoked directly and the readiness check returns `status=fail`, announce that TechPlan will invoke the governance publish CLI to copy reviewed BusinessPlan artifacts and then launch the native architecture workflow via `bmad-lens-bmad-skill`. Confirm before any publication, copy, or write action. If the user does not confirm, stop cleanly with no changes.
13. If mode is `interactive` and TechPlan was auto-delegated from `/next` and the readiness check returns `status=fail`, treat that delegation as already confirmed. Do not ask a redundant yes/no prompt; proceed directly into the phase entry sequence.
14. Publish staged BusinessPlan artifacts, including the businessplan review report when present, into the governance docs mirror via the CLI-backed `bmad-lens-git-orchestration publish-to-governance --phase businessplan` operation before creating TechPlan outputs. Do not create governance files or directories directly with tool calls or patches; the publish CLI performs that copy.
15. Load BusinessPlan artifacts from the staged control-repo docs path for authoring context, and use the governance mirror as the published snapshot for cross-feature consumers.
16. Load cross-feature context via `bmad-lens-init-feature` `fetch-context --depth full`.
17. Load domain constitution via `bmad-lens-constitution`.
18. Delegate to `bmad-lens-bmad-skill --skill bmad-create-architecture`. After delegation, do not continue with conductor-side architecture questions or authoring. The native architecture workflow owns the interactive session and document creation; TechPlan resumes only for phase completion once the staged architecture artifact exists.

## Artifacts

| Artifact | Description | Agent |
|----------|-------------|-------|
| `architecture.md` | System design, data model, API design, ADRs | bmad-lens-bmad-skill (`bmad-create-architecture`) |

## Required Frontmatter

```yaml
---
feature: {featureId}
doc_type: architecture
status: draft | in-review | approved
goal: "{one-line goal}"
key_decisions: []
open_questions: []
depends_on: []
blocks: []
updated_at: {ISO timestamp}
---
```

## Phase Completion

When all lifecycle-required techplan artifacts are staged in the control repo:

1. Run `bmad-lens-adversarial-review --phase techplan --source phase-complete` using `phases.techplan.completion_review` from `lifecycle.yaml` before updating phase state. Do not run this gate during batch pass 1. In interactive mode and batch pass 2:
	- If the verdict is `fail`, stop and do not update `feature.yaml`.
	- If the verdict is `pass` or `pass-with-warnings`, continue.
2. Update `feature.yaml` phase to `techplan-complete` via `bmad-lens-feature-yaml`.
3. Leave governance publication of the architecture doc and techplan review report to the FinalizePlan handoff unless the user explicitly requests publication now.
4. Report next action: advance to `/finalizeplan` (auto-advance with promotion per lifecycle.yaml).

## Integration Points

| Skill / Agent | Role in TechPlan |
|---------------|-------------------|
| `bmad-lens-feature-yaml` | Reads feature.yaml; updates phase after completion |
| `bmad-lens-init-feature` | Loads cross-feature context and optional named-service governance context |
| `bmad-lens-constitution` | Loads domain constitution for architectural constraints |
| `bmad-lens-git-orchestration` | Publishes reviewed BusinessPlan artifacts to governance and stages TechPlan drafts locally |
| `bmad-lens-bmad-skill` | Routes architecture creation through the Lens-aware BMAD wrapper with planning-doc write boundaries |
| `bmad-lens-theme` | Applies active persona overlay |
