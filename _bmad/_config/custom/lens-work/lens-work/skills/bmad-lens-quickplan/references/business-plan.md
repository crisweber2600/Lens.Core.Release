# Business Plan

## Purpose

The business plan captures the *why* behind a feature: the business need, stakeholder expectations, success criteria, and risks. It is always a separate document from the tech plan — never combined, regardless of feature size.

The analyst role (`bmad-agent-analyst`) is responsible for writing the business plan. QuickPlan invokes the analyst and provides context; the analyst produces the document.

## Inputs

| Input | Source | Required |
|-------|--------|----------|
| Feature context | `feature.yaml` (loaded on activation) | Yes |
| Cross-feature context | Related feature summaries + depends_on full docs (loaded via `bmad-lens-git-state`) | Auto |
| Domain constitution | Loaded via `bmad-lens-constitution` | Auto |
| User clarifications | Interactive prompt or batch defaults | On demand |

## Process

1. **Load context** — QuickPlan provides the analyst with: feature.yaml contents, related feature summaries, domain constitution, any user-supplied context.
2. **Analyst writes the plan** — Invoke `bmad-agent-analyst` with full context. The analyst produces a draft `business-plan.md`.
3. **Frontmatter validation** — QuickPlan runs `validate-frontmatter --doc-type business-plan` on the output before committing.
4. **Auto-publish** — Atomic two-phase commit via `./references/auto-publish.md`.
5. **Phase update** — Update `feature.yaml` phase to `businessplan` via `bmad-lens-feature-yaml`.

## Output: `business-plan.md`

Required location: `{governance-repo}/features/{domain}/{service}/{featureId}/business-plan.md` on `main`.

### Required Frontmatter

```yaml
---
feature: {featureId}
doc_type: business-plan
status: draft
goal: "{one-line business goal}"
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
| **Executive Summary** | One paragraph: why this feature, what problem it solves, who benefits |
| **Business Context** | Market or internal driver; what happens if this is not built |
| **Stakeholders** | Who requested it, who is affected, who signs off |
| **Success Criteria** | Measurable outcomes; how success is evaluated post-launch |
| **Scope** | What is in scope; explicit out-of-scope items |
| **Risks and Mitigations** | Business risks (not technical); probability and mitigation per risk |
| **Dependencies** | Other features or external systems this depends on |
| **Open Questions** | Unresolved business questions that could change scope |
| **Timeline Expectations** | Any business-driven deadline or urgency |

## Interactive Mode Behaviour

After producing the draft:
1. Show a one-paragraph summary of the plan.
2. Surface any open questions from frontmatter.
3. Ask for confirmation before committing: `[business-plan] Ready to commit? (y/n)`
4. On confirmation, commit and report: `[business-plan] committed → {short-sha}`

## Batch Mode Behaviour

### Pass 1 — Intake Generation

- Do not produce or commit `business-plan.md` on pass 1.
- Add only unresolved business-planning questions to `quickplan-batch-input.md`.
- Stop after the intake file is written or refreshed.

### Pass 2 — Execute Business Plan

- Once `quickplan-batch-input.md` contains answers for every required question block, produce and commit the business plan using the approved answers as context.
- Append a one-line business-plan summary to the batch report.
- Proceed to tech plan only if the pipeline remains unblocked.

## Quality Checklist (pre-commit)

- [ ] Frontmatter passes `validate-frontmatter`
- [ ] All required sections present
- [ ] `goal` is a single line under 120 characters
- [ ] `success_criteria` are measurable (not "improve performance")
- [ ] Risks have at least one mitigation each
- [ ] `depends_on` references valid feature IDs
