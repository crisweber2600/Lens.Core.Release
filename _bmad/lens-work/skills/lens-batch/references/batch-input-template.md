# {Target} Batch Input

```yaml
---
feature: {featureId}
doc_type: batch-input
phase: {target}
goal: "{one-line planning goal}"
context_sources: []
updated_at: {ISO timestamp}
---
```

## How To Use This File

1. Review the context snapshot below.
2. Fill in the answer area for every question that still needs input.
3. If a question has no extra constraints, say so explicitly instead of leaving it blank.
4. Re-run `/batch` or the owning phase command with `--mode batch`.

Lens automatically treats the file as ready when every required answer block contains real content. Blank answers and placeholders such as `TBD`, `TODO`, `?`, or `[pending]` are treated as unresolved.

## Context Snapshot

- Feature: `{featureId}`
- Target: `{target}`
- Current phase: `{current_phase}`
- Track: `{track}`
- Docs path: `{docs_path}`
- Predecessor artifacts reviewed: `{predecessor_summary}`
- Cross-feature context: `{cross_feature_summary}`
- Constitution notes: `{constitution_summary}`

## Questions To Answer

### Q1

**Why this matters:** {why_this_question_exists}

**Question:** {targeted_question}

**Your answer:**

### Q2

**Why this matters:** {why_this_question_exists}

**Question:** {targeted_question}

**Your answer:**

## Additional Notes

- Add any clarifications that should be treated as hard constraints on pass 2.
- If an answer invalidates an existing artifact, say so explicitly here.