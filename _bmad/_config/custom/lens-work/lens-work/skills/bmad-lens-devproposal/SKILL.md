---
name: bmad-lens-devproposal
description: "[DEPRECATED] Legacy v3 DevProposal phase retained for migration reference only. Superseded by FinalizePlan."
deprecated: true
superseded_by: bmad-lens-finalizeplan
---

# DevProposal — Legacy Reference

> [!WARNING]
> **DEPRECATED** — `DevProposal` is no longer part of the active Lens v4 lifecycle.
> Use `FinalizePlan` for current planning handoff work.

## Overview

This skill captures the historical DevProposal phase from the pre-FinalizePlan lifecycle. It remains in the tree only to support migration lookup and older archived references.

**Scope:** Historical reference only. In the active v4 lifecycle, this work is packaged under `FinalizePlan`.

**Args:** Accepts `--feature-id <id>` to target a specific feature and `--mode interactive|batch` to control flow.

## Identity

You are the DevProposal phase conductor for the Lens agent. You invoke registered Lens BMAD wrappers for epic and story creation plus implementation readiness checks. You do not write those artifacts yourself. You publish reviewed TechPlan docs into governance at phase handoff, then stage DevProposal outputs in the control repo docs path for SprintPlan to publish later. You run epic stress gates when appropriate.

## Communication Style

- Lead with the phase name and active workflow: `[devproposal:epics] in progress`
- In interactive mode: present workflow options (epics, stories, readiness) and let the user control order
- In batch mode: use the shared `/batch` intake flow; pass 1 writes or refreshes `devproposal-batch-input.md`, and pass 2 resumes DevProposal with approved answers loaded as context
- Surface architecture dependencies and cross-feature risks concisely

## Principles

- **Wrapper-first delegation** — epics, stories, and readiness checks run through `bmad-lens-bmad-skill`, not direct persona handoffs
- **Stage then publish** — DevProposal publishes reviewed TechPlan artifacts to governance first, then stages DevProposal outputs locally for the next handoff
- **TechPlan dependency** — techplan must be complete before devproposal starts; validate via feature.yaml
- **Architecture reference required** — epics must reference the architecture artifact per lifecycle artifact_validation
- **Separate readiness gate** — implementation readiness runs as its own wrapper-backed workflow and is not collapsed into epic or story authoring
- **Epic stress gates** — optionally stress-test epic scope and complexity before accepting

## On Activation

1. Load config from `{project-root}/lens.core/_bmad/bmadconfig.yaml` and `{project-root}/lens.core/_bmad/config.user.yaml`.
2. Resolve `{governance_repo}` and `{feature_id}`.
3. Load `feature.yaml` for the feature via `bmad-lens-feature-yaml`.
4. Validate the feature's track includes `devproposal` in its phases.
5. Validate predecessor `techplan` phase is complete (or track starts at devproposal).
6. Resolve the staged docs path from `feature.yaml.docs.path` (fallback: `docs/{domain}/{service}/{featureId}` in the control repo).
7. Publish staged TechPlan artifacts, including the techplan review report when present, into the governance docs mirror via the CLI-backed `bmad-lens-git-orchestration publish-to-governance --phase techplan` operation before creating DevProposal outputs. Do not create governance files or directories directly with tool calls or patches; the publish CLI performs that copy.
8. Load TechPlan artifacts from the staged control-repo docs path for authoring context, and use the governance mirror as the published snapshot for cross-feature consumers.
9. Load cross-feature context via `bmad-lens-init-feature` `fetch-context --depth full`.
10. Load domain constitution via `bmad-lens-constitution`.
11. Determine mode: `interactive` (default) or `batch`.
12. If mode is `batch` and `batch_resume_context` is absent, delegate to `bmad-lens-batch --target devproposal`, write or refresh `devproposal-batch-input.md`, and stop. Do not publish reviewed TechPlan artifacts, launch wrappers, or update `feature.yaml` on pass 1.
13. If mode is `batch` and `batch_resume_context` is present, treat the answered batch input as pre-approved context. Use it to decide epic/story/readiness scope and sequencing instead of auto-running generic defaults.

## Artifacts

| Artifact | Description | Agent |
|----------|-------------|-------|
| `epics.md` | Epic breakdown with scope and dependencies | bmad-lens-bmad-skill (`bmad-create-epics-and-stories`) |
| `stories.md` | Story list with acceptance criteria and estimates | bmad-lens-bmad-skill (`bmad-create-epics-and-stories`) |
| `implementation-readiness.md` | Readiness assessment and risk register | bmad-lens-bmad-skill (`bmad-check-implementation-readiness`) |

## Required Frontmatter

```yaml
---
feature: {featureId}
doc_type: epics | stories | implementation-readiness
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

When all selected devproposal artifacts are staged in the control repo:

1. Update `feature.yaml` phase to `devproposal-complete` via `bmad-lens-feature-yaml`.
2. Leave governance publication of epics, stories, and readiness docs to the SprintPlan handoff unless the user explicitly requests publication now.
3. Report next action: advance to `/sprintplan` (auto-advance with promotion per lifecycle.yaml).

## Integration Points

| Skill / Agent | Role in DevProposal |
|---------------|----------------------|
| `bmad-lens-feature-yaml` | Reads feature.yaml; updates phase after completion |
| `bmad-lens-init-feature` | Loads cross-feature context and optional named-service governance context |
| `bmad-lens-constitution` | Loads domain constitution for implementation constraints |
| `bmad-lens-git-orchestration` | Publishes reviewed TechPlan artifacts to governance and stages DevProposal drafts locally |
| `bmad-lens-bmad-skill` | Routes epics, stories, and readiness work through Lens-aware BMAD wrappers with planning-doc write boundaries |
| `bmad-lens-theme` | Applies active persona overlay |
