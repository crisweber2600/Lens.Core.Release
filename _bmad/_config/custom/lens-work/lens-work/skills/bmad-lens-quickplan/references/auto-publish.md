# Auto-Publish

## Purpose

Auto-publish ensures every planning artifact is committed atomically to governance `main`: the full document, the extracted summary, and the index update all land in a single logical operation. There is no "commit now, sync later" — if the commit fails, the artifact is not committed at all.

## The Atomic Commit

Every artifact commit is a single atomic operation on governance `main`, coordinated via `bmad-lens-git-orchestration`:

### Step 1 — Validate

1. Validate frontmatter (via `quickplan-ops.py validate-frontmatter`).

### Step 2 — Write Full Artifact to Main

1. Write the full artifact file to `{governance-repo}/features/{domain}/{service}/{featureId}/{artifact}` on `main`.
2. Extract summary from the artifact frontmatter (via `quickplan-ops.py extract-summary`).
3. Write `{governance-repo}/features/{domain}/{service}/{featureId}/summary.md` on `main` — creating or updating it.
4. Update `{governance-repo}/feature-index.yaml` on `main` — add or update the feature entry with `phase`, `goal`, `updated_at`, and `doc_types_present`.
5. Commit all files together with message: `feat({featureId}): add {artifact} + update summary and index`

If the commit fails (e.g., merge conflict on main), report the error and halt.

## Commit Message Format

| Phase | Format |
|-------|--------|
| Artifact commit | `feat({featureId}): add {artifact} + update summary and index` |
| Stories batch | `feat({featureId}): add {N} stories (sprint {sprintNumber})` |

## Summary.md Format

The `summary.md` on main is a lightweight snapshot for cross-feature context loading:

```markdown
# Summary: {featureId}

**Phase:** {current phase}
**Goal:** {goal from frontmatter}
**Status:** {status from most recent planning doc}
**Updated:** {updated_at}

## Key Decisions

{key_decisions list from most recent planning doc}

## Open Questions

{open_questions list from most recent planning doc}

## Artifacts Present

{list of artifact files present in the feature directory on main}
```

## feature-index.yaml Entry Format

```yaml
{featureId}:
  domain: {domain}
  service: {service}
  phase: {phase}
  track: {track}
  goal: "{goal}"
  updated_at: "{ISO timestamp}"
  docs_present:
    - business-plan
    - tech-plan
    - sprint-plan
    - stories
```

## Idempotency

Auto-publish is safe to retry:
- If the artifact already exists with the same content, skip the commit.
- If the index already reflects the current artifact (same `updated_at`), skip the update.
- Never create duplicate commits.

## Error Handling

| Error | Action |
|-------|--------|
| Frontmatter validation failure | Halt before commit; report validation errors |
| Commit failure | Halt; report error with governance repo details |
| Merge conflict on main | Report conflict details; suggest `git pull` and retry |
| Partial write (summary OK, index fails) | Attempt index update again; report if it fails twice |

## Integration

Auto-publish is invoked at the end of every pipeline phase:

```
[business-plan] → auto-publish → [tech-plan] → auto-publish → ...
```

QuickPlan calls `bmad-lens-git-orchestration` to perform the actual git operations. Auto-publish in this reference file defines the contract; git-orchestration implements it.
