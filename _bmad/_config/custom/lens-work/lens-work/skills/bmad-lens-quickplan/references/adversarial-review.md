# Adversarial Review

## Purpose

Adversarial review stress-tests both the business plan and tech plan for flaws before stories are created. It is comprehensive — not a rubber stamp — and replaces the traditional PR-per-milestone ceremony. A weak adversarial review that misses real problems is worse than no review.

QuickPlan runs adversarial review autonomously (no external agent invocation). The output is a `adversarial-review.md` artifact committed to governance `main`.

## Inputs

| Input | Source | Required |
|-------|--------|----------|
| Business plan | `business-plan.md` from governance `main` | Yes |
| Tech plan | `tech-plan.md` from governance `main` | Yes |
| Cross-feature context | Summaries + full docs for depends_on features | Auto |
| Domain constitution | Architecture constraints and non-negotiables | Auto |

## Review Dimensions

Adversarial review must cover all five dimensions. Missing any dimension is a quality failure.

### 1. Logic Flaws

Look for internal inconsistencies and faulty reasoning:
- Does the tech plan actually achieve the business goal?
- Are success criteria reachable with the proposed approach?
- Are there circular dependencies between features?
- Does the rollout strategy contradict the testing strategy?
- Are any ADRs in conflict with each other?

### 2. Coverage Gaps

Look for what is missing or assumed:
- Are there user flows described in the business plan with no corresponding technical component?
- Are there API contracts with no data model to back them?
- Are there dependencies listed with no integration plan?
- Is observability defined for all new failure modes?
- Are there rollback steps for every rollout phase?

### 3. Complexity and Risk

Look for underestimated work and hidden complexity:
- Are any scope items understated relative to their technical surface area?
- Does the data migration strategy account for production data volume?
- Is the phasing realistic given the listed dependencies?
- Are there single points of failure in the architecture that are not acknowledged?

### 4. Cross-Feature Dependencies

Look for conflicts and missing coordination with related features:
- Do any listed `depends_on` features have contradicting design decisions?
- Does this feature's timeline conflict with a feature it depends on?
- Are there features blocked by this one that are not listed in `blocks`?
- Does the API contract of this feature clash with the assumptions of a dependent feature?

### 5. Assumptions and Blind Spots

Look for things taken for granted:
- What must be true for the plan to succeed that is not stated?
- Which external systems are assumed to be stable or available?
- Are there regulatory, compliance, or security constraints not addressed?
- Is there team or skill availability assumed but not confirmed?

## Severity Ratings

| Severity | Meaning | Required Action |
|----------|---------|-----------------|
| **Critical** | Plan cannot proceed as-is; will cause failure | Must resolve before sprint planning |
| **High** | Significant risk; likely to cause rework or delay | Should resolve; document decision if accepted |
| **Medium** | Notable gap; manageable but adds risk | Document and track as open question |
| **Low** | Minor improvement; no blocking impact | Optional; note for future reference |

## Output: `adversarial-review.md`

Required location: `{governance-repo}/features/{domain}/{service}/{featureId}/adversarial-review.md` on `main`.

### Structure

```markdown
# Adversarial Review: {featureId}

**Reviewed:** {ISO timestamp}
**Business Plan SHA:** {short-sha}
**Tech Plan SHA:** {short-sha}
**Overall Rating:** pass | pass-with-warnings | fail

## Summary

{One paragraph: key findings, overall verdict, and recommended next action}

## Findings

### Critical

| # | Dimension | Finding | Recommendation |
|---|-----------|---------|----------------|
| C1 | Logic Flaws | ... | ... |

### High

| # | Dimension | Finding | Recommendation |
|---|-----------|---------|----------------|
| H1 | Coverage Gaps | ... | ... |

### Medium / Low

...

## Accepted Risks

{Any findings accepted as-is, with rationale}

## Open Questions Surfaced

{New questions uncovered by the review that should be added to plan frontmatter}
```

## Pipeline Integration

| Condition | Action |
|-----------|--------|
| `pass` (no findings or low only) | Proceed to sprint planning |
| `pass-with-warnings` (medium/high findings, all documented) | Proceed to sprint planning; include high findings in sprint plan as explicit risks |
| `fail` (any critical finding) | **Stop.** Surface critical findings. In interactive mode, prompt user for resolution direction. In batch mode, halt and report findings — do not create stories. |

## Interactive Mode Behaviour

1. Run review; produce `adversarial-review.md`.
2. Show finding count by severity.
3. For `fail`: surface critical findings inline and halt. Ask: `[adversarial-review] Critical findings require resolution. Address now? (y/n)`
4. For `pass` or `pass-with-warnings`: report finding summary. Ask: `[adversarial-review] Committed. Proceed to sprint planning? (y/n)`

## Batch Mode Behaviour

### Pass 1 — Intake Generation

- Do not run adversarial review on pass 1.
- Add only unresolved review-readiness questions to `quickplan-batch-input.md`.
- Stop after the intake file is written or refreshed.

### Pass 2 — Review Gate

- Run review and commit the artifact once `quickplan-batch-input.md` contains answers for every required question block.
- On `pass` or `pass-with-warnings`, continue the pipeline.
- On `fail`, halt the pipeline and report all critical findings in the final output. Do not proceed to sprint planning or story creation.

### Batch Reporting

- Include finding counts by severity and the final gate outcome in the batch summary.
