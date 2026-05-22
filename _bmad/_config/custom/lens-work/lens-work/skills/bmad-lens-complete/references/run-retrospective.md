# Run Retrospective

Trigger the retrospective workflow for a feature before archiving.

## Outcome

A `retrospective.md` file exists in the feature directory, capturing what went well, what didn't, key learnings, and delivery metrics.

## When to Use

This is the first step of the complete workflow. Always run (or confirm skip) before proceeding to finalize. The retrospective must exist before `archive-status` is set to `archived`.

## Pre-conditions

- Feature is in `dev` phase (or phase is `complete` with no retrospective yet)
- Feature directory exists in governance repo

## Process

Delegate to the retrospective skill:

```bash
# The retrospective skill handles the full workflow.
# Invoke it with the feature context:
#   bmad-lens-retrospective --feature-id {featureId} --governance-repo {governance_repo}
```

If the retrospective skill is unavailable, prompt the user to create `retrospective.md` manually in the feature directory with the following sections:

```markdown
# Retrospective: {feature name}

**Feature:** {featureId}
**Completed:** {ISO date}

## What Went Well

## What Didn't Go Well

## Key Learnings

## Metrics

- Planned duration:
- Actual duration:
- Stories completed:
- Bugs found post-merge:

## Action Items
```

## Output

After retrospective completes, confirm:

```
✓ retrospective.md written to {feature-dir}/retrospective.md
```

If the user explicitly wants to skip retrospective, require explicit confirmation:

> "Confirm skip retrospective? This will be noted in the archive summary. (yes/no)"

Only proceed on explicit `yes`. Record the skip in the final summary.
