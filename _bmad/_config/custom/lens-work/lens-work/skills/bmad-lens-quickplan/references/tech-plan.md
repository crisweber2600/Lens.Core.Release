# Tech Plan

## Purpose

The tech plan captures the *how*: system design decisions, architecture changes, API contracts, data model impacts, and rollout strategy. It is always a separate document from the business plan — never combined, regardless of feature size.

The architect role (`bmad-agent-architect`) is responsible for writing the tech plan. QuickPlan invokes the architect with the completed business plan and cross-feature context.

## Inputs

| Input | Source | Required |
|-------|--------|----------|
| Business plan | `business-plan.md` from governance `main` | Yes |
| Feature context | `feature.yaml` | Yes |
| Cross-feature context | Related feature summaries + depends_on full docs | Auto |
| Domain constitution | Technical constraints and architecture principles | Auto |
| User clarifications | Interactive prompt or batch defaults | On demand |

## Process

1. **Load context** — QuickPlan provides the architect with: completed business plan, feature.yaml, cross-feature context, domain constitution.
2. **Architect writes the plan** — Invoke `bmad-agent-architect` with full context. The architect produces a draft `tech-plan.md`.
3. **Frontmatter validation** — QuickPlan runs `validate-frontmatter --doc-type tech-plan` on the output before committing.
4. **Auto-publish** — Atomic two-phase commit via `./references/auto-publish.md`.
5. **Phase update** — Update `feature.yaml` phase to `techplan` via `bmad-lens-feature-yaml`.

## Output: `tech-plan.md`

Required location: `{governance-repo}/features/{domain}/{service}/{featureId}/tech-plan.md` on `main`.

### Required Frontmatter

```yaml
---
feature: {featureId}
doc_type: tech-plan
status: draft
goal: "{one-line technical goal}"
key_decisions: []
open_questions: []
depends_on: []
blocks: []
updated_at: {ISO timestamp}
---
```

### Required Sections

| Section | Content |
|---------|---------|
| **Technical Summary** | One paragraph: the core technical approach and what changes in the system |
| **Architecture Overview** | System context diagram or description; components affected; integration points |
| **Design Decisions (ADRs)** | Each significant decision as: Decision / Rationale / Alternatives Rejected |
| **API Contracts** | New or changed API endpoints; request/response shapes; breaking change flag |
| **Data Model Changes** | Schema additions, alterations, or migrations; backward compatibility |
| **Dependencies** | External services, libraries, or other features this relies on |
| **Rollout Strategy** | Feature flags, phased rollout, canary, or immediate; rollback plan |
| **Testing Strategy** | Unit, integration, and e2e test coverage expectations |
| **Observability** | Metrics, logs, and alerts added or changed |
| **Open Questions** | Unresolved technical questions that could affect the design |

## Interactive Mode Behaviour

After producing the draft:
1. Show the architecture overview and list of key ADRs.
2. Surface any open questions from frontmatter.
3. Ask for confirmation before committing: `[tech-plan] Ready to commit? (y/n)`
4. On confirmation, commit and report: `[tech-plan] committed → {short-sha}`

## Batch Mode Behaviour

### Pass 1 — Intake Generation

- Do not produce or commit `tech-plan.md` on pass 1.
- Add only unresolved technical-design questions to `quickplan-batch-input.md`.
- Stop after the intake file is written or refreshed.

### Pass 2 — Execute Tech Plan

- Once `quickplan-batch-input.md` contains answers for every required question block, produce and commit the tech plan using the approved answers as context.
- Append a one-line tech-plan summary to the batch report.
- Proceed to adversarial review only if the pipeline remains unblocked.

## Quality Checklist (pre-commit)

- [ ] Frontmatter passes `validate-frontmatter`
- [ ] All required sections present
- [ ] Every ADR has rationale and at least one rejected alternative
- [ ] API contracts include breaking change flag (true/false)
- [ ] Rollout strategy includes an explicit rollback plan
- [ ] `depends_on` matches or is a superset of business plan `depends_on`
- [ ] Tech plan `goal` aligns with business plan `goal` without contradicting it
