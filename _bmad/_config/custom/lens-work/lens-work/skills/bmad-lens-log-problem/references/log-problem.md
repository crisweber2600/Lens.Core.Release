# Log Problem

Append a problem entry to the feature's `problems.md`.

## Outcome

A tagged problem entry is appended to `{governance-repo}/features/{domain}/{service}/{featureId}/problems.md`. The file is created if it does not exist. The entry has a unique ID, phase tag, and category tag.

## Process

Collect the required fields. If the caller is another skill (headless mode), all fields must be passed as arguments. If the user invoked this interactively, prompt for any missing fields.

Run the log operation:

```bash
python3 ./scripts/log-problem-ops.py log \
  --governance-repo {governance_repo} \
  --feature-id {featureId} \
  --domain {domain} \
  --service {service} \
  --phase {phase} \
  --category {category} \
  --title "{short title}" \
  --description "{full description}"
```

**To preview without writing:**

```bash
python3 ./scripts/log-problem-ops.py log ... --dry-run
```

## Required Fields

| Field | Values | Notes |
|-------|--------|-------|
| `--phase` | `preplan`, `businessplan`, `techplan`, `finalizeplan`, `dev`, `complete` | Auto-detect from feature.yaml if available |
| `--category` | `requirements-gap`, `execution-failure`, `dependency-issue`, `scope-creep`, `tech-debt`, `process-breakdown` | Ask once if unclear |
| `--title` | Short string | One line, imperative or noun phrase |
| `--description` | Full string | What happened and why it matters |

## Output

```json
{
  "status": "pass",
  "entry_id": "prob-20260406T020334Z",
  "problems_path": "/path/to/features/platform/identity/auth-login/problems.md",
  "problem": {
    "entry_id": "prob-20260406T020334Z",
    "title": "Missing index on users table",
    "phase": "dev",
    "category": "tech-debt",
    "description": "Query on users table has no index; causes 2s delays at scale",
    "status": "open"
  }
}
```

## After Logging

Confirm to the user (or calling skill) in one line:

```
Logged: prob-20260406T020334Z [dev/tech-debt]
```

In headless mode, emit only the JSON. Do not surface the confirmation line.
