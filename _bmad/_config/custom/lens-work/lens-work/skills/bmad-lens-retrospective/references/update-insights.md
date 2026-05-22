# Update Insights

Append new patterns discovered in this feature's retrospective to the user's `insights.md` — the cross-feature learning store.

## When to Use

- After generating retrospective.md and confirming findings
- When the user says "update insights" or "feed forward to insights"
- In batch mode: after generate-report completes

## Process

Run the update-insights operation:

```bash
python3 ./scripts/retrospective-ops.py update-insights \
  --insights-file {governance_repo}/users/{username}/insights.md \
  --patterns '{patterns_json}' \
  --feature-id {featureId}
```

Pass `--dry-run` to preview the append without writing:

```bash
python3 ./scripts/retrospective-ops.py update-insights \
  --insights-file {governance_repo}/users/{username}/insights.md \
  --patterns '{patterns_json}' \
  --feature-id {featureId} \
  --dry-run
```

The `--patterns` argument accepts the `patterns` array from the analyze output as a JSON string.

## Output JSON

```json
{
  "status": "pass",
  "insights_path": "/path/to/users/alice/insights.md",
  "new_patterns": 2,
  "dry_run": false
}
```

`dry_run: true` when `--dry-run` was passed. File is not modified in dry-run mode.

## Insights.md Format

The script appends a new section for this feature. If `insights.md` does not exist, it is created with a header before the first entry.

**Created file header:**
```markdown
# Lens Insights

Cross-feature patterns and lessons learned. Updated automatically by the retrospective skill.

---
```

**Appended section (one per retrospective run):**
```markdown
## {featureId} — {ISO date}

{N} patterns identified.

| Category | Count | Phases | Pattern |
|----------|-------|--------|---------|
| requirements-gap | 4 | businessplan, techplan | repeated in planning phases |
| execution-failure | 3 | dev | clustered in dev phase |

**Key Takeaway:** {dominant pattern category} was the primary failure mode. Watch for this in future features.

---
```

## Idempotency

The script checks whether an entry for `{featureId}` already exists in insights.md before appending. If it does, it appends a new entry with the date to avoid silent overwrites. Duplicate detection is by feature ID header match.

## When insights.md Doesn't Exist

The script creates the file, including the header, then appends the first entry. The parent directory must exist. If the parent directory is missing, the operation fails with `insights_dir_not_found`.

## Presenting Results (Interactive Mode)

Before writing, show the user what will be appended:

> "I'll add 2 patterns for feature `my-feature` to insights.md:
> - requirements-gap (4 occurrences, planning phases)
> - execution-failure (3 occurrences, dev phase)
> 
> Proceed? (yes/no)"

After writing, confirm the path and number of new patterns added.

## Errors

| Error | Exit Code | Cause |
|-------|-----------|-------|
| `insights_dir_not_found` | 1 | Parent directory of `--insights-file` does not exist |
| `invalid_patterns_json` | 1 | `--patterns` argument is not valid JSON |
| `insights_write_failed` | 1 | Cannot write to insights file |
