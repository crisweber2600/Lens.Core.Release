# Feature Overview

Surface all features by domain/service with phase, track, status, and staleness alerts.

## Outcome

A structured table of every feature indexed in `feature-index.yaml` on `main`, grouped by domain, with visual indicators for stale features — enabling rapid status assessment across all active work.

## Process

Run the collect operation:

```bash
python3 ./scripts/dashboard-ops.py collect \
  --governance-repo {governance_repo}
```

The output includes a `features` array, `stale_count`, and `domain_count`. Each feature entry contains `featureId`, `name`, `domain`, `service`, `phase`, `track`, `priority`, `stale` (bool), and `lastUpdated`.

To surface the overview as an HTML section, run `generate` instead:

```bash
python3 ./scripts/dashboard-ops.py generate \
  --governance-repo {governance_repo} \
  --output ./lens-dashboard.html
```

## Staleness Definition

A feature is **stale** when:
- Its `phase` is one of `dev`, `finalizeplan`, `businessplan`, or `techplan` (active phases)
- Its `lastUpdated` timestamp is more than **14 days** ago, or `lastUpdated` is absent

Stale features are flagged with `"stale": true` in the collect output and rendered with a `STALE` badge and a dedicated alert section at the top of the dashboard.

## Display

Present as a table grouped by domain, with columns: Feature ID, Name, Domain, Service, Phase, Track, Priority. Color-code rows by status:
- `planning` phases → blue left border
- `dev` phase → orange left border
- `complete` → green, muted
- `paused` / `archived` → gray, muted

List all stale features by name in the staleness alert section at the top of the page.
