# List Features

Discover and enumerate features in the governance repo.

## Outcome

A structured list of all features with their identity, phase, track, priority, and location — enabling discovery and status overview across the governance repo.

## Process

Run the list operation:

```bash
python3 ./scripts/feature-yaml-ops.py list \
  --governance-repo {governance_repo}
```

Optional filters to narrow results:

```bash
python3 ./scripts/feature-yaml-ops.py list \
  --governance-repo {governance_repo} \
  --phase dev \
  --domain platform \
  --track quickplan
```

Returns JSON with a `features` array and `total` count. Each entry includes featureId, name, domain, service, phase, track, priority, and path.

For user-facing display, present as a table grouped by domain/service. Highlight features in active phases (`dev`, `finalizeplan`) and any with `critical` priority.
