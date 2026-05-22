# Root Cause Report

Generate a `retrospective.md` for the feature — a concise root cause analysis with findings and recommendations.

## When to Use

- After analyzing problems.md and reviewing the pattern summary
- When the user says "generate the retrospective" or "write the retrospective report"
- In batch mode: immediately after analyze completes

## Process

Run the generate-report operation:

```bash
python3 ./scripts/retrospective-ops.py generate-report \
  --problems-file {feature_dir}/problems.md \
  --feature-id {featureId} \
  --output {feature_dir}/retrospective.md
```

## Output JSON

```json
{
  "status": "pass",
  "report_path": "/path/to/feature/retrospective.md",
  "patterns_found": 2,
  "recommendations": 3
}
```

## Report Structure

The generated `retrospective.md` follows this structure:

```markdown
# Retrospective: {feature name}

**Feature ID:** {featureId}  
**Date:** {ISO date}  
**Problems Logged:** {total} ({open} open, {resolved} resolved)

## Summary

{1–2 sentence headline: dominant pattern and what it indicates}

## Findings

### Finding 1: {Category Name} — {count} occurrences

**Phases affected:** {phase list}  
**Pattern:** {pattern description}

{2–3 sentence explanation of why this happened based on the problems}

### Finding 2: ...

## Recommendations

1. **{Short action title}** — {1 sentence explanation of what to change}
2. ...

## Open Problems

{If any problems are still open, list them with GitHub Issue links if available}

| Problem | Phase | Category | GitHub Issue |
|---------|-------|----------|-------------|
| {title} | {phase} | {category} | {#issue or "—"} |

## Archive

Problems logged: {total}. Retrospective generated: {ISO date}.
```

## Writing Guidance

**Summary:** One headline sentence naming the dominant pattern. One sentence stating what it indicates about the feature development process.

**Findings:** Cover only patterns (categories with 3+ occurrences) and any phase with >40% concentration. Do not enumerate individual problems. Explain the underlying cause, not just what happened.

**Recommendations:** Each recommendation must be specific and actionable. "Improve requirements" is not a recommendation. "Define acceptance criteria before entering techplan" is.

**Open Problems section:** Only include if there are unresolved problems. This signals work needed before archive.

## Errors

| Error | Exit Code | Cause |
|-------|-----------|-------|
| `problems_file_not_found` | 1 | `--problems-file` path does not exist |
| `output_write_failed` | 1 | Cannot write to `--output` path |
