# Resume Feature

Reactivate a paused feature, restoring it to its pre-pause phase and clearing all pause state.

## Outcome

The feature.yaml is updated: `phase` is restored to the value stored in `paused_from`, and `paused_from`, `pause_reason`, and `paused_at` are cleared.

## Process

Run the resume operation:

```bash
python3 ./scripts/pause-resume-ops.py resume \
  --governance-repo {governance_repo} \
  --feature-id {featureId} \
  --domain {domain} \
  --service {service}
```

To preview without making changes:

```bash
python3 ./scripts/pause-resume-ops.py resume \
  --governance-repo {governance_repo} \
  --feature-id {featureId} \
  --domain {domain} \
  --service {service} \
  --dry-run
```

## Validations

- Feature must exist (else exit 1)
- Feature must currently be in `paused` phase (else exit 1: "Feature is not paused")
- `paused_from` must be set (else exit 1: "No paused_from phase to restore")

## Output

On success, the script outputs JSON:

```json
{
  "status": "pass",
  "feature_id": "auth-login",
  "resumed_to_phase": "techplan",
  "was_paused_since": "2026-04-06T02:03:34Z"
}
```

## Context Restoration

After resume, load the feature context so the agent is ready to continue work:

1. Read `feature.yaml` in full for current state
2. Check for a `summary.md` or `context.md` in the feature directory
3. Note the open problems count if available from feature state
4. Present the restored phase and context to the user so work can continue immediately
