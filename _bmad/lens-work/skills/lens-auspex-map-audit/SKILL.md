---
name: lens-auspex-map-audit
description: Lens wrapper for auditing Auspex Two-Tree topology, stable IDs, parent refs, and derived map readiness.
---

## Follow-up Questions

Use `vscode_askQuestions` for all follow-up questions instead of freeform chat prompts.

# Lens Auspex Map Audit

## Overview

Thin Lens conductor for Auspex topology audit. It resolves Lens context and constitution gates, keeps the workflow read-first, then delegates to `.agents/skills/ausx-map-audit/SKILL.md`.

Use this as the preferred first check for cumulative project knowledge, derived maps, orphaned features, broken parent references, empty ledgers, and completed features that have not been promoted.

## On Activation

1. Run:

```bash
uv run --script lens.core/_bmad/lens-work/skills/lens-preflight/scripts/light-preflight.py --caller lens-auspex-map-audit
```

2. Resolve feature context from explicit input, `.lens/personal/context.yaml`, then governance `feature.yaml`.
3. Require `domain`, `service`, `feature_id`, `track`, `phase`, and `docs.path`.
4. Resolve constitution gates with `lens-constitution` for the active domain and service, display them, and stop on violations.
5. Enforce write scope: this wrapper may write only audit reports under configured `reporting_output_path`, normally `_bmad-output/auspex`. Do not write to `NextLensV3.Release`.
6. Load `.agents/skills/ausx-map-audit/SKILL.md` and delegate the audit request.

## Audit Contract

The audit should treat feature and landscape metadata as source truth, and any governance map as a rebuildable projection. It should report orphans, invalid `belongs_to` references, mismatched parent-child declarations, missing ledgers, stale reports, and projection rebuild blockers.
