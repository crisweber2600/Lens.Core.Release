# Read Feature State

Load and present feature state from a feature.yaml file.

## Outcome

The caller receives structured feature data — identity, lifecycle state, team, dependencies, and metadata — parsed from the feature.yaml file.

## Process

Run the read operation:

```bash
python3 ./scripts/feature-yaml-ops.py read \
  --governance-repo {governance_repo} \
  --feature-id {featureId}
```

Returns JSON with the full feature state. If `--field` is specified, returns only that field's value.

For user-facing display, present a progressive summary: identity and phase first, then details on request.
