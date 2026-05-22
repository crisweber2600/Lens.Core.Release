# Analyze Problems

Parse and analyze the feature's `problems.md` to identify patterns, phase concentrations, and category distributions.

## When to Use

- At the start of any retrospective flow
- When the user asks "what patterns do we have?" or "analyze our problems"
- Before generating retrospective.md or updating insights.md

## Process

Run the analyze operation:

```bash
python3 ./scripts/retrospective-ops.py analyze \
  --problems-file {feature_dir}/problems.md
```

If `problems.md` does not exist, inform the user and ask whether to create a blank one or abort.

## Output

```json
{
  "status": "pass",
  "total": 12,
  "open": 4,
  "resolved": 8,
  "by_phase": {
    "businessplan": 2,
    "techplan": 5,
    "dev": 5
  },
  "by_category": {
    "requirements-gap": 4,
    "execution-failure": 3,
    "technical-debt": 2,
    "process-gap": 2,
    "unknown": 1
  },
  "patterns": [
    {
      "category": "requirements-gap",
      "count": 4,
      "phases": ["businessplan", "techplan"],
      "pattern": "repeated in planning phases"
    }
  ]
}
```

`patterns` contains entries for any category that appears 3 or more times. The `pattern` field is a short narrative description of where the category concentrated.

## Interpreting the Output

**Phase concentration:** If one phase contains >40% of all problems, that phase has a structural issue worth calling out in the retrospective.

**Category distribution:** If one category accounts for >30% of problems, it is the primary finding. Lead the retrospective with it.

**Pattern detection:** A `patterns` entry means the category recurred enough to be systemic — not a one-off. Treat these as root causes, not symptoms.

**Open vs resolved:** If open > 30% of total at retrospective time, flag that unresolved problems need GitHub Issues before the feature is archived.

## Presenting Results to the User (Interactive Mode)

Lead with the headline pattern:

> "12 problems logged. The dominant pattern is **requirements-gap** (4 problems, concentrated in techplan and businessplan). This suggests planning phases are underspecified before execution begins."

Then offer to drill down or proceed to report generation.

## Errors

| Error | Exit Code | Cause |
|-------|-----------|-------|
| `problems_file_not_found` | 1 | `--problems-file` path does not exist |
| `problems_file_empty` | 0 | File exists but has no problem entries — returns zero counts |
