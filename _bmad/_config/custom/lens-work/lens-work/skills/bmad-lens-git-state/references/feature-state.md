# Feature State

## Outcome

Produce a complete picture of a feature's lifecycle state by reading its `feature.yaml` metadata from the governance repo's `main` branch — surfaces any metadata issues.

## Process

Run:
```
./scripts/git-state-ops.py feature-state \
  --governance-repo {governance_repo} \
  --feature-id {featureId}
```

The script returns JSON. Present the following to the user:

**Phase & Track** — from `feature.yaml` (authoritative)
**YAML on Main** — whether the feature.yaml exists on `main` (governance never branches)
**Discrepancies** — cases where feature.yaml metadata is inconsistent
**Status** — current lifecycle status

The governance repo stays on `main` — no feature branches are created there. Branch topology (`{featureId}` + `{featureId}-plan`) only exists in the control repo.

If `feature.yaml` is missing, report clearly: this feature has no governance record and prompt the user to run the `bmad-lens-feature-yaml` skill to create one.

## Output Fields

| Field | Source | Description |
| ----- | ------ | ----------- |
| `feature_id` | feature.yaml | Canonical identifier |
| `phase` | feature.yaml | Current lifecycle phase |
| `track` | feature.yaml | Execution track |
| `status` | feature.yaml | `active`, `paused`, `complete`, or `warning` |
| `yaml_on_main` | git | Whether `feature.yaml` exists on governance `main` |
| `yaml_path` | git | Resolved path to `feature.yaml` in governance repo |
| `discrepancies` | derived | Conflicts in YAML metadata state |
