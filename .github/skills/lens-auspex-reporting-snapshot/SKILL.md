---
name: lens-auspex-reporting-snapshot
description: Lens wrapper for creating Auspex read-only stakeholder reporting snapshots.
---

## Follow-up Questions

Use `vscode_askQuestions` for all follow-up questions instead of freeform chat prompts.

# Lens Auspex Reporting Snapshot

## Overview

Thin Lens conductor for read-only reporting snapshots. It validates Lens context and gates, then delegates to `.agents/skills/ausx-reporting-snapshot/SKILL.md`.

Snapshots are stakeholder views. They are not source truth and must not mutate feature archives, ledgers, governance maps, or topology decisions.

## On Activation

1. Run:

```bash
uv run --script lens.core/_bmad/lens-work/skills/lens-preflight/scripts/light-preflight.py --caller lens-auspex-reporting-snapshot
```

2. Resolve feature context from explicit input, `.lens/personal/context.yaml`, then governance `feature.yaml`.
3. Require `domain`, `service`, `feature_id`, `track`, `phase`, and `docs.path`.
4. Resolve and display constitution gates with `lens-constitution` for the active domain and service. Stop on violations.
5. Enforce write scope: this wrapper writes only generated Markdown and JSON snapshots under `_bmad-output/auspex` or an explicitly approved reporting output directory. Do not write to `NextLensV3.Release`.
6. Load `.agents/skills/ausx-reporting-snapshot/SKILL.md` and delegate the snapshot request.

## Snapshot Contract

The JSON output must remain stable for future UI ingestion and include at least `module`, `report_type`, `created_at`, `scope`, `overall_status`, `blocking`, `advisory`, `features`, `ledgers`, `salmon_impacts`, and `freshness`.
