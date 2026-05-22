# Generate Dashboard

Produce a complete, self-contained HTML dashboard file.

## Outcome

A single HTML file at the specified output path containing all dashboard sections: feature overview, dependency graph, problem heatmap, sprint progress, team view, and retrospective trends. No external dependencies — the file is fully portable.

## Process

```bash
python3 ./scripts/dashboard-ops.py generate \
  --governance-repo {governance_repo} \
  --output ./lens-dashboard.html
```

With a custom template:

```bash
python3 ./scripts/dashboard-ops.py generate \
  --governance-repo {governance_repo} \
  --output ./lens-dashboard.html \
  --template ./path/to/custom-template.html
```

Returns JSON on completion:

```json
{
  "status": "pass",
  "output_path": "/absolute/path/to/lens-dashboard.html",
  "features_included": 12,
  "generated_at": "2026-04-06T02:03:34Z"
}
```

## Data Sources

| Section | Source | Branch |
|---------|--------|--------|
| Feature Overview | `feature-index.yaml` | `main` |
| Dependency Graph | `feature-index.yaml` | `main` |
| Problem Heatmap | `features/{domain}/{service}/{feature-id}/problems.md` | `main` |
| Sprint Progress | `features/{domain}/{service}/{feature-id}/summary.md` | `main` |
| Team View | User daily logs | `main` |
| Retrospective Trends | `features/{domain}/{service}/{feature-id}/retrospective.md` | `main` |

## Graceful Degradation

When a feature's deep content files (`problems.md`, `retrospective.md`) are not found on `main`, the corresponding section shows "unavailable" rather than an error. The `generate` command always produces a valid HTML file regardless of file availability.

## Template Placeholders

The default template (`assets/dashboard-template.html`) uses these placeholders:

| Placeholder | Content |
|-------------|---------|
| `{{TITLE}}` | Dashboard title |
| `{{GENERATED_AT}}` | ISO 8601 generation timestamp |
| `{{STALE_ALERTS}}` | Alert block for stale features (empty if none) |
| `{{FEATURE_OVERVIEW_TABLE}}` | HTML table of all features |
| `{{DEPENDENCY_GRAPH_SVG}}` | Inline SVG dependency graph |
| `{{PROBLEM_HEATMAP_TABLE}}` | Problem count by phase |
| `{{SPRINT_PROGRESS_TABLE}}` | Active feature sprint status |
| `{{TEAM_VIEW_TABLE}}` | Team activity table |
| `{{RETRO_TRENDS_TABLE}}` | Retrospective patterns table |

## Errors

| Condition | Response |
|-----------|----------|
| `--governance-repo` path does not exist | `{"status": "fail", "error": "Governance repo not found: ..."}`, exit 1 |
| Template file not found | `{"status": "fail", "error": "Dashboard template not found"}`, exit 1 |
| `feature-index.yaml` not on `main` | Dashboard generates with empty feature list; warning in output |
