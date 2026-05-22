# Sprint Planning

## Purpose

Sprint planning converts the tech plan and adversarial review findings into an ordered set of sprints, each containing fully specified user stories. The output is two artifacts: `sprint-plan.md` (the sprint structure) and individual story files in `stories/`.

## Inputs

| Input | Source | Required |
|-------|--------|----------|
| Tech plan | `tech-plan.md` from governance `main` | Yes |
| Business plan | `business-plan.md` — for success criteria and scope boundaries | Yes |
| Adversarial review | `adversarial-review.md` — high findings become explicit sprint risks | Yes |
| Feature context | `feature.yaml` — track, priority, and team | Yes |

## Phase 1: Sprint Plan

### Process

1. Extract all technical deliverables from the tech plan.
2. Identify dependencies between deliverables (intra-feature ordering).
3. Group deliverables into sprints: each sprint has a clear goal and is independently shippable where possible.
4. Include adversarial review high findings as explicit risk items in the relevant sprints.
5. Estimate relative complexity per story (S/M/L/XL or story points — match the team's convention from feature.yaml or config).
6. Validate that sprint 1 contains no unresolved critical blockers.
7. Validate frontmatter with `validate-frontmatter --doc-type sprint-plan`.
8. Commit via auto-publish.
9. Update `feature.yaml` phase to `finalizeplan`.

### Output: `sprint-plan.md`

Required location: `{governance-repo}/features/{domain}/{service}/{featureId}/sprint-plan.md`

#### Required Frontmatter

```yaml
---
feature: {featureId}
doc_type: sprint-plan
status: draft
goal: "{one-line sprint plan goal}"
key_decisions: []
open_questions: []
depends_on: []
blocks: []
updated_at: {ISO timestamp}
---
```

#### Required Sections

| Section | Content |
|---------|---------|
| **Sprint Overview** | Table: sprint number, goal, stories, complexity total, risks |
| **Sprint N** | One section per sprint: goal, story list with IDs, acceptance criteria summary, risks |
| **Cross-Sprint Dependencies** | Stories that gate other sprints |
| **Definition of Done** | Shared DoD applied to all stories in this plan |

## Phase 2: Story Creation

After `sprint-plan.md` is committed, create individual story files for every story in every sprint.

### Story File Location

```
{governance-repo}/features/{domain}/{service}/{featureId}/stories/{storyId}.md
```

Story ID format: `{featureId}-{sprintNumber}-{storyNumber}` — e.g., `auth-login-1-01`.

### Story File Structure

Each story file must contain:

```markdown
# Story: {storyId}

## Context

**Feature:** {featureId}
**Sprint:** {sprintNumber}
**Priority:** {priority}
**Estimate:** {S|M|L|XL}

## User Story

As a {role}, I want {capability}, so that {benefit}.

## Acceptance Criteria

- [ ] {Criterion 1}
- [ ] {Criterion 2}
...

## Technical Notes

{Relevant tech plan sections; design decisions; integration points this story touches}

## Dependencies

**Blocked by:** {story IDs this story cannot start until complete}
**Blocks:** {story IDs that cannot start until this story is complete}

## Definition of Done

{Sprint plan DoD, copied verbatim}

## Open Questions

{Any story-level questions; reference adversarial review findings if applicable}
```

### Story Creation Process

1. For each sprint in the sprint plan, for each story in that sprint:
   a. Create the story file with full context from the tech plan, business plan, and sprint plan.
   b. The `Technical Notes` section must include all information the implementing agent will need — do not assume the agent will read the tech plan independently.
2. After all stories are created, commit the entire `stories/` directory as a single atomic commit via auto-publish.

### Story Quality Checklist

- [ ] Every acceptance criterion is independently verifiable
- [ ] `Technical Notes` contains enough context for implementation without reading the tech plan
- [ ] `Dependencies` are correct and consistent with the sprint plan
- [ ] No story has an XL estimate without a note explaining why it was not split
- [ ] DoD is copied verbatim from the sprint plan

## Interactive Mode Behaviour

**Sprint plan phase:**
1. Show sprint overview table.
2. Ask: `[sprint-plan] Ready to commit? (y/n)`
3. Commit and report: `[sprint-plan] committed → {short-sha}`

**Story creation phase:**
1. Show count: `Creating {N} stories across {M} sprints...`
2. Create all stories.
3. Ask: `[stories] {N} stories created. Commit all? (y/n)`
4. Commit and report: `[stories] committed → {short-sha}`

## Batch Mode Behaviour

### Pass 1 — Intake Generation

- Do not create `sprint-plan.md` or story files on pass 1.
- Add only unresolved sprint-boundary, estimation, and story-shaping questions to `quickplan-batch-input.md`.
- Stop after the intake file is written or refreshed.

### Pass 2 — Execute Sprint Planning

- Once `quickplan-batch-input.md` contains answers for every required question block, create the sprint plan and all story files using the approved answers as context.
- Commit each planning stage as an atomic two-phase commit.
- Append sprint and story counts to the batch summary log.
