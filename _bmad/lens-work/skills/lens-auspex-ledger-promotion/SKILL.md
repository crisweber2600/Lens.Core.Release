---
name: lens-auspex-ledger-promotion
description: Lens wrapper for promoting completed feature knowledge into Auspex living service, domain, or program ledgers.
---

## Follow-up Questions

Use `vscode_askQuestions` for all follow-up questions instead of freeform chat prompts.

# Lens Auspex Ledger Promotion

## Overview

Thin Lens conductor for ledger promotion. It validates Lens context, constitution gates, and write boundaries before delegating to `.agents/skills/ausx-ledger-promotion/SKILL.md`.

Ledger promotion moves durable interpretation upward into living ledgers. It does not move feature archives.

## On Activation

1. Run:

```bash
uv run --script lens.core/_bmad/lens-work/skills/lens-preflight/scripts/light-preflight.py --caller lens-auspex-ledger-promotion
```

2. Resolve feature context from explicit input, `.lens/personal/context.yaml`, then governance `feature.yaml`.
3. Require `domain`, `service`, `feature_id`, `track`, `phase`, `docs.path`, and target repo mapping before any write.
4. Resolve and display constitution gates with `lens-constitution` for the active domain and service. Stop on violations.
5. Enforce write scope:
   - reports may be written under `_bmad-output/auspex`
   - ledger updates require explicit `--apply`
   - ledgers may be written only under the configured landscape root
   - feature archives under `docs/features/` must never be moved
   - `NextLensV3.Release` is read-only source material and must not be written
6. Load `.agents/skills/ausx-ledger-promotion/SKILL.md` and delegate the promotion request.

## Promotion Contract

Promoted knowledge must preserve traceability to feature IDs and source artifacts. If the promotion discovers upstream impact, route the operator to `lens-auspex-salmon-impact` rather than silently editing unrelated ledgers.
