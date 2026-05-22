# Resolve Rules

Resolves the effective governance constitution for a given domain/service scope by merging the 4-level hierarchy additively.

## When to Use

Call this before any workflow that needs to know what rules apply: plan workflows, compliance checks, dashboard rendering, onboarding guidance.

## Required Context

- Governance repo path (local checkout)
- `domain` — from `feature.yaml`
- `service` — from `feature.yaml`
- `repo` (optional) — for repo-level rules

## Output

```json
{
  "domain": "platform",
  "service": "auth",
  "repo": null,
  "levels_loaded": ["org", "domain", "service"],
  "resolved_constitution": {
    "permitted_tracks": ["quickplan", "full"],
    "required_artifacts": {
      "planning": ["business-plan", "tech-plan"],
      "dev": ["stories"]
    },
    "gate_mode": "informational",
    "additional_review_participants": ["security-team"],
    "enforce_stories": true,
    "enforce_review": true
  }
}
```

## Script Usage

```bash
uv run scripts/constitution-ops.py resolve \
  --governance-repo /path/to/governance-repo \
  --domain platform \
  --service auth \
  [--repo my-repo]
```

## Key Behaviors

- If `org/constitution.md` is missing → error (org level is required)
- If domain or service constitution is missing → silently skip that level (use next-higher defaults)
- Parse errors in a constitution file → warning in output, continue with defaults for that level
- Missing fields in a constitution file → filled from org defaults or system defaults

## Merge Strategy

Each field merges differently as constitutions are applied org → domain → service → repo:

| Field | Strategy | Notes |
|-------|----------|-------|
| `permitted_tracks` | Intersection | Empty intersection → `[]` with warning |
| `required_artifacts` | Union per phase | Artifacts accumulate; no duplicates |
| `gate_mode` | Strongest wins | `hard` beats `informational` |
| `additional_review_participants` | Union | Reviewers accumulate across levels |
| `enforce_stories` | Strongest wins | `true` beats `false` |
| `enforce_review` | Strongest wins | `true` beats `false` |

When `enforce_stories=true`, `"stories"` is automatically added to `required_artifacts["dev"]`.

## Constitution File Format

Files are Markdown with YAML frontmatter. Only the frontmatter block is machine-parsed:

```markdown
---
permitted_tracks: [full, quickplan]
required_artifacts:
  planning: [security-review]
gate_mode: hard
additional_review_participants: [security-team]
enforce_stories: true
enforce_review: false
---
# Prose documentation (ignored by script, shown to humans)

This service handles PII data. All PRs require security review...
```

All fields are optional — omitted fields are inherited from higher levels or system defaults.

## Warnings in Output

The `warnings` array reports non-fatal issues detected during resolution:

| Warning type | Trigger |
|-------------|---------|
| `parse_error` | Constitution file has invalid YAML (non-org levels only) |
| `unknown_constitution_keys` | Constitution file contains unrecognized field names |
| `unknown_gate_mode` | `gate_mode` value is not `hard` or `informational` |
| `unknown_tracks` | `permitted_tracks` contains unrecognized track names |
| `empty_permitted_tracks` | Intersection resolved to `[]` |

## Defaults (when no constitution file exists at a level)

```yaml
permitted_tracks: [quickplan, full, hotfix, tech-change]
required_artifacts:
  planning: [business-plan, tech-plan]
  dev: [stories]
gate_mode: informational
additional_review_participants: []
enforce_stories: false
enforce_review: false
```
