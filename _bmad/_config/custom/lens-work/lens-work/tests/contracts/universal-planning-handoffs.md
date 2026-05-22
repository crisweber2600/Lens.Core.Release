# Universal Planning Handoffs Contract

This contract captures the staged planning and wrapper-routing behavior for the Lens lifecycle rollout.

## Scope

- Included: `preplan`, `businessplan`, `techplan`, `finalizeplan`, `quickplan`, and `/dev` handoff behavior.
- Excluded: `expressplan` remains unchanged in this rollout.

## Phase Entry Publication

| Command | Reviewed predecessor published on entry | Current outputs stay staged locally |
|---------|-----------------------------------------|-------------------------------------|
| `/businessplan` | PrePlan set (`product-brief`, `research`, `brainstorm`) | `prd`, `ux-design` |
| `/techplan` | BusinessPlan set (`prd`, `ux-design`) | `architecture`, optional techplan review report |
| `/finalizeplan` | TechPlan set (`architecture`, optional techplan review report) | `finalizeplan-review`, `epics`, `stories`, `implementation-readiness`, `sprint-status`, story files |
| `/dev` | FinalizePlan set (`finalizeplan-review`, `epics`, `stories`, `implementation-readiness`, `sprint-status`, story files) | none; implementation begins after publication |

## Wrapper Routing

| Command | Work item | Required Lens wrapper |
|---------|-----------|-----------------------|
| `/preplan` | brainstorming | `bmad-brainstorming` |
| `/preplan` | product brief | `bmad-product-brief` |
| `/preplan` | research | `bmad-domain-research` or `bmad-market-research` or `bmad-technical-research` |
| `/businessplan` | PRD | `bmad-create-prd` |
| `/businessplan` | UX design | `bmad-create-ux-design` |
| `/techplan` | architecture | `bmad-create-architecture` |
| `/finalizeplan` | epics and stories | `bmad-create-epics-and-stories` |
| `/finalizeplan` | implementation readiness | `bmad-check-implementation-readiness` |
| `/finalizeplan` | sprint planning | `bmad-sprint-planning` |
| `/finalizeplan` | story files | `bmad-create-story` |

## Interactive Handoff Boundary

| Command | Interactive confirmation happens | Native workflow owns after delegation | Conductor must not do |
|---------|----------------------------------|---------------------------------------|-----------------------|
| `/businessplan` | Before any publication or artifact writes only when BusinessPlan was invoked directly; if auto-delegated from `/next`, the workflow selection remains interactive but the phase entry itself is already confirmed | `bmad-create-prd` or `bmad-create-ux-design` menus, discovery questions, and document authorship | Ask PRD or UX discovery questions itself, silently continue to the second selected workflow, or ask a second yes/no prompt just because `/next` launched BusinessPlan |
| `/techplan` | Before any publication or artifact writes only when TechPlan was invoked directly; if auto-delegated from `/next`, phase entry is already confirmed | `bmad-create-architecture` menus, discovery questions, and document authorship | Ask architecture-discovery questions itself, write `architecture.md` before delegation, or ask a second yes/no prompt just because `/next` launched TechPlan |

If `/businessplan` interactive mode selects `both`, each native workflow runs as a separate handoff. BusinessPlan must ask before launching the second workflow.

When `/next` auto-delegates into a lifecycle command, that handoff counts as consent to start the delegated phase. The delegated phase may still ask for scope choices that are intrinsic to the phase, but it must not pause for a redundant "confirm to proceed" gate.

The Lens BMAD wrapper is context-only. After delegation it does not continue phase-conductor execution or synthesize downstream planning artifacts on behalf of the delegated workflow.

## Story File Compatibility

The sprint handoff must recognize all currently supported story-file layouts:

- `dev-story-*.md` and `dev-story-*.yaml`
- `{epic}-{story}-{slug}.md` and `{epic}-{story}-{slug}.yaml`
- `stories/{story-id}.md` and `stories/{story-id}.yaml`

If none of these shapes are present for FinalizePlan output, `/dev` must halt instead of silently continuing.