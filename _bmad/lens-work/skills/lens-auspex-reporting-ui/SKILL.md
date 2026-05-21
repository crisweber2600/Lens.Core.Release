---
name: lens-auspex-reporting-ui
description: Lens wrapper for maintaining the Auspex MVP1 reporting UI data contract and non-deployable snapshot baseline.
---

## Follow-up Questions

Use `vscode_askQuestions` for all follow-up questions instead of freeform chat prompts.

# Lens Auspex Reporting UI

## Overview

Thin Lens conductor for the Auspex MVP1 reporting UI contract. It does not create or deploy a Kubernetes UI from this repo. It maintains the Lens-side read-only data contract, documentation, and snapshot foundation for a future app target repo.

When current status data is needed, delegate snapshot generation to `.agents/skills/ausx-reporting-snapshot/SKILL.md`.

## On Activation

1. Run:

```bash
uv run --script lens.core/_bmad/lens-work/skills/lens-preflight/scripts/light-preflight.py --caller lens-auspex-reporting-ui
```

2. Resolve feature context from explicit input, `.lens/personal/context.yaml`, then governance `feature.yaml`.
3. Require `domain`, `service`, `feature_id`, `track`, `phase`, and `docs.path`.
4. Resolve and display constitution gates with `lens-constitution` for the active domain and service. Stop on violations.
5. Enforce write scope:
   - contract docs may live under target repo `docs/`
   - generated snapshot artifacts may live only under `_bmad-output/auspex`
   - no UI app, cluster manifest, or write-back workflow is introduced here
   - `NextLensV3.Release` is read-only source material and must not be written
6. For data production, load `.agents/skills/ausx-reporting-snapshot/SKILL.md`. For contract maintenance, use `docs/auspex-reporting-ui-contract.md` as the governing artifact.

## UI Contract

MVP1 is a read-only contract: project rollup, feature lifecycle, artifact reader metadata, search/filter fields, freshness, source failures, and access abstraction. Repository artifacts remain source truth.
