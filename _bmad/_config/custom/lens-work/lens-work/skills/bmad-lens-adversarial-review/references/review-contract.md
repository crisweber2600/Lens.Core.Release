# Lens Lifecycle Adversarial Review Contract

## Purpose

Lifecycle adversarial review stress-tests the just-finished planning phase before the next handoff begins. It is not a ceremony and it is not a rubber stamp. The review must challenge the current artifact set, identify what is missing, and push the user to surface assumptions they did not realize they were making.

This contract applies to staged completion reviews for `preplan`, `businessplan`, and `techplan`.

## Inputs

| Input | Source | Required |
|-------|--------|----------|
| Current phase artifacts | Staged docs path in the control repo | Yes |
| Predecessor reviewed artifacts | Staged docs path and governance mirror when available | Phase-dependent |
| Cross-feature context | `bmad-lens-init-feature fetch-context --depth full` | Auto |
| Domain constitution | `bmad-lens-constitution` | Auto |
| Feature lifecycle state | `feature.yaml` | Yes |

## Review Dimensions

Every lifecycle review must cover all five dimensions.

### 1. Logic Flaws

Look for internal inconsistencies and faulty reasoning:
- Does this phase output actually support the next phase handoff?
- Do the current artifact decisions contradict the feature goal, predecessor context, or constitution?
- Are there circular dependencies, impossible transitions, or broken success assumptions?

### 2. Coverage Gaps

Look for what is missing or assumed:
- Are there requirements, user flows, or technical dependencies with no treatment in the current phase artifacts?
- Does the phase introduce decisions without documenting downstream implications?
- Are rollout, observability, risk, or operational requirements left implicit?

### 3. Complexity and Risk

Look for underestimated work and hidden complexity:
- Does the artifact set understate the technical or organizational surface area?
- Are there risky sequencing assumptions, vague migrations, or unclear execution boundaries?
- Are there single points of failure that are not acknowledged?

### 4. Cross-Feature Dependencies

Look for conflicts and missing coordination with related features:
- Do listed dependencies or blocked features disagree with the proposed plan?
- Does this phase assume decisions from another feature or service that are not confirmed?
- Are there external systems or teams implicitly on the critical path?

### 5. Assumptions and Blind Spots

Look for what everyone is taking for granted:
- What must be true for this phase handoff to succeed that is not stated?
- Which operational, security, compliance, or staffing constraints are silently assumed?
- What has the team probably not thought about yet?

## Severity Ratings

| Severity | Meaning | Required Action |
|----------|---------|-----------------|
| `Critical` | The next phase should not proceed as-is | Must resolve before phase completion |
| `High` | Significant risk or likely rework | Document and explicitly accept or address |
| `Medium` | Notable gap with manageable risk | Track as open question or follow-up |
| `Low` | Minor improvement opportunity | Optional follow-up |

## Party-Mode Challenge Round

After the adversarial findings are drafted, run a short party-mode challenge round.

Required behavior:
- Use 2-3 distinct planning personas relevant to the phase.
- Keep the exchange to one critique round per persona.
- Use `Name (Role): dialogue` formatting.
- Focus on blind spots, weak assumptions, hidden dependencies, and handoff failures.
- End with 3-5 direct challenge questions for the user.

The goal is not consensus. The goal is to force missing thinking into the open.

## Output Structure

Write the phase review artifact to the staged docs path using this structure:

```markdown
# Adversarial Review: {featureId} / {phase}

**Reviewed:** {ISO timestamp}
**Source:** phase-complete | manual-rerun
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

{Any findings the user explicitly accepts, with rationale}

## Party-Mode Challenge

Name (Role): ...

## Gaps You May Not Have Considered

1. ...
2. ...
3. ...

## Open Questions Surfaced

{Questions that should be reflected back into planning artifacts or feature metadata}
```

## Verdict Rules

| Condition | Verdict |
|-----------|---------|
| Any unresolved critical finding or missing required artifact | `fail` |
| No critical findings, but medium/high findings remain documented | `pass-with-warnings` |
| No unresolved material gaps remain | `pass` |

## Gate Behavior

| Source | Verdict | Action |
|--------|---------|--------|
| `phase-complete` | `fail` | Stop. Do not mark the phase complete. |
| `phase-complete` | `pass` or `pass-with-warnings` | Allow the phase conductor to continue completion. |
| `manual-rerun` | any | Update the review artifact and report the verdict only. |