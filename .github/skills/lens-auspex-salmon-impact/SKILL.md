---
name: lens-auspex-salmon-impact
description: Lens wrapper for reviewing Auspex upstream-impact signals and recursive topology consistency risk.
---

## Follow-up Questions

Use `vscode_askQuestions` for all follow-up questions instead of freeform chat prompts.

# Lens Auspex Salmon Impact

## Overview

Thin Lens conductor for Salmon impact review. It runs Lens safety checks, then delegates to `.agents/skills/ausx-salmon-impact/SKILL.md`.

Salmon signals are non-blocking by default. The recursive consistency findings may still identify blockers.

## On Activation

1. Run:

```bash
uv run --script lens.core/_bmad/lens-work/skills/lens-preflight/scripts/light-preflight.py --caller lens-auspex-salmon-impact
```

2. Resolve feature context from explicit input, `.lens/personal/context.yaml`, then governance `feature.yaml`.
3. Require `domain`, `service`, `feature_id`, `track`, `phase`, and `docs.path`.
4. Resolve and display constitution gates with `lens-constitution` for the active domain and service. Stop on violations.
5. Enforce write scope: this wrapper writes only Salmon reports under `_bmad-output/auspex` unless a later approved workflow explicitly applies ledger updates. Do not write to `NextLensV3.Release`.
6. Load `.agents/skills/ausx-salmon-impact/SKILL.md` and delegate the review request.

## Review Contract

Traverse upward from the origin feature or artifact to service, domain, and program assumptions, then downward into affected siblings and ledgers. Classify findings as advisory or blocking based on discovered impact, not on the signal itself.
