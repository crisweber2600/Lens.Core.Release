# Active Features

## Outcome

Enumerate all features in the governance repo by scanning `feature.yaml` files on `main` — providing a workspace-wide inventory of in-flight work based on governance metadata.

## Process

Run:
```
./scripts/git-state-ops.py active-features \
  --governance-repo {governance_repo} \
  [--domain {domain}] \
  [--phase {phase}] \
  [--track {track}]
```

The script scans for `feature.yaml` files under the repo's features directory on `main` and returns a combined list. The governance repo stays on `main` — no feature branches exist there. Apply filter flags to narrow the scope.

Present as a table with columns: Feature ID, Phase, Track, Status.

If a `feature.yaml` has invalid content or no feature_id, flag it as a **ghost** — YAML exists but is malformed or incomplete.

## Filter Options

| Flag | Description | Example |
| ---- | ----------- | ------- |
| `--domain` | Filter by domain | `--domain payments` |
| `--phase` | Filter by lifecycle phase | `--phase dev` |
| `--track` | Filter by execution track | `--track hotfix` |

## Output Structure

```json
{
  "features": [
    {
      "feature_id": "payments-checkout-v2",
      "domain": "payments",
      "service": "checkout",
      "phase": "dev",
      "track": "full",
      "status": "active",
      "yaml_path": "features/payments/checkout/payments-checkout-v2/feature.yaml"
    }
  ],
  "ghost_yamls": [],
  "total_active": 1
}
```
