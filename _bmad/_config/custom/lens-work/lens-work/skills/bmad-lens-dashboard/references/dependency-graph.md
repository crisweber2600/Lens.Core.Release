# Dependency Graph

Visualize blocking and dependency relationships between features.

## Outcome

A dependency graph showing which features depend on, block, or relate to other features — sourced from `feature-index.yaml` on `main`. Rendered as an SVG embedded in the dashboard HTML.

## Process

Run the dependency-data operation to extract graph data:

```bash
python3 ./scripts/dashboard-ops.py dependency-data \
  --governance-repo {governance_repo}
```

Returns `nodes` (one per feature) and `edges` (one per dependency relationship):

```json
{
  "status": "pass",
  "nodes": [
    {"id": "auth-login", "name": "User Authentication", "domain": "platform", "status": "dev"}
  ],
  "edges": [
    {"from": "auth-login", "to": "user-profile", "type": "depends_on"}
  ]
}
```

## Edge Types

| Type | Color | Meaning |
|------|-------|---------|
| `depends_on` | Red | This feature cannot proceed until the target is complete |
| `blocks` | Orange | This feature blocks the target from progressing |
| `related` | Gray | Related work with no hard dependency |

## Node Layout

Nodes are laid out in a grid (up to 6 columns) and colored by phase status:
- `planning` → blue
- `dev` → orange
- `complete` → green
- `archived` / `paused` → gray

## Data Source

Dependency data is read exclusively from `feature-index.yaml` on `main`. No plan branch access is needed for this section. If `feature-index.yaml` is absent or unreadable, the graph section displays "No features to display".
