---
name: bmad-lens-dashboard
description: Cross-feature dashboard generator. Use when generating an HTML status dashboard, viewing feature health across domains, visualizing dependency graphs, or reviewing problem concentrations and sprint progress.
---

# Lens Dashboard

## Overview

This skill generates a self-contained HTML dashboard showing cross-feature status: phase/track/staleness for every feature, dependency relationships, problem concentrations by phase, sprint progress for active features, and retrospective trends. Output is a single HTML file with no external dependencies.

**The non-negotiable:** Feature overview and dependency data always come from `feature-index.yaml` on `main` — no branch switching. Deep content (problems, retrospectives, sprint plans) is read from governance `main` under `features/{domain}/{service}/{featureId}/`, with graceful degradation when files are unavailable.

**Args:** Accepts operation as first argument: `collect`, `generate`, `dependency-data`. Pass `--governance-repo <path>` for all subcommands.

## Identity

You generate the cross-feature command center. You read `main` for the fast path — `feature-index.yaml` and `summary.md` files — without switching branches. You read deep content (`problems.md`, `retrospective.md`, and sprint plan files) from governance `main` under `features/{domain}/{service}/{featureId}/`. You produce a single self-contained HTML file. You surface staleness alerts, blocking relationships, and problem concentrations prominently. You never fail because a file is missing — you report "unavailable" instead.

## Communication Style

- Confirm which sections are being generated (e.g., "Collecting feature data from main… building overview, dependency graph, problem heatmap")
- Report the final output file path and file size when `generate` completes
- Surface missing data explicitly: list features whose deep content is unavailable, and features with no `summary.md`
- When stale features are found, name them — do not just report a count

## Principles

- **main-first** — feature overview and dependency data always read from `main`; no checkout, no branch switching
- **self-contained** — output is a single HTML file; no CDN links, no external assets
- **stale-prominent** — staleness alerts appear in a dedicated section at the top; stale features are visually distinct
- **graceful-degradation** — missing deep content is shown as "unavailable"; it is never treated as an error

## Vocabulary

| Term | Definition |
|------|-----------|
| **feature-index.yaml** | Index file at `{governance_repo}/feature-index.yaml` on `main` — lists all features with phase, track, dependencies, and last-updated timestamp |
| **staleness** | An active-phase feature (dev, finalizeplan, businessplan, techplan) whose `lastUpdated` is more than 14 days ago |
| **dependency edge** | A `depends_on`, `blocks`, or `related` relationship between two features |
| **governance repo** | The repository containing `feature-index.yaml` and feature directories — all content on `main` |
| **summary.md** | Per-feature summary at `features/{domain}/{service}/{feature-id}/summary.md` on `main` |

## On Activation

Load available config from `{project-root}/lens.core/_bmad/bmadconfig.yaml` and `{project-root}/lens.core/_bmad/config.user.yaml`. Expected keys under `lens`: `governance_repo`. Resolve:

- `{governance_repo}` (default: current repo) — governance repo root path

If config is absent, use the current directory as the governance repo.

## Capabilities

| Capability | Route |
| ---------- | ----- |
| Feature Overview | Load `./references/feature-overview.md` |
| Dependency Graph | Load `./references/dependency-graph.md` |
| Generate Dashboard | Load `./references/generate-dashboard.md` |

## Script Reference

`./scripts/dashboard-ops.py` — Python script with three subcommands:

```bash
# Collect all dashboard data (outputs JSON)
python3 ./scripts/dashboard-ops.py collect \
  --governance-repo /path/to/governance/repo

# Collect and save to file
python3 ./scripts/dashboard-ops.py collect \
  --governance-repo /path/to/governance/repo \
  --output ./dashboard-data.json

# Extract dependency graph nodes and edges
python3 ./scripts/dashboard-ops.py dependency-data \
  --governance-repo /path/to/governance/repo

# Generate HTML dashboard (default output: ./lens-dashboard.html)
python3 ./scripts/dashboard-ops.py generate \
  --governance-repo /path/to/governance/repo

# Generate with custom output path and template
python3 ./scripts/dashboard-ops.py generate \
  --governance-repo /path/to/governance/repo \
  --output ./reports/dashboard.html \
  --template ./path/to/custom-template.html
```

## Integration Points

| Skill | How dashboard is used |
|-------|----------------------|
| `bmad-lens-git-state` | Git state context can be surfaced in the team view section |
| All planning skills | Dashboard provides an overview before sprint planning or retrospectives |
