# Pause Feature

Mark a feature as paused, preserving its current phase so work can resume exactly where it left off.

## Outcome

The feature.yaml is updated: `phase` is set to `paused`, `paused_from` stores the previous phase, `pause_reason` stores the required reason, and `paused_at` stores the current UTC timestamp.

## Process

Run the pause operation:

```bash
python3 ./scripts/pause-resume-ops.py pause \
  --governance-repo {governance_repo} \
  --feature-id {featureId} \
  --domain {domain} \
  --service {service} \
  --reason "{reason}"
```

The `--reason` flag is required. If the user has not provided a reason, ask for one before proceeding.

To preview without making changes:

```bash
python3 ./scripts/pause-resume-ops.py pause \
  --governance-repo {governance_repo} \
  --feature-id {featureId} \
  --domain {domain} \
  --service {service} \
  --reason "{reason}" \
  --dry-run
```

## Validations

- Feature must exist (else exit 1)
- Feature must not already be paused (else exit 1: "Feature is already paused")
- Reason must be non-empty (else exit 1: "Pause reason is required")

## Output

On success, the script outputs JSON:

```json
{
  "status": "pass",
  "feature_id": "auth-login",
  "paused_from": "techplan",
  "reason": "Blocked on upstream API contract",
  "paused_at": "2026-04-06T02:03:34Z"
}
```

After the pause completes, confirm to the user:
- Feature ID paused
- Phase preserved (`paused_from`)
- Reason stored
- Timestamp
