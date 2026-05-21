---
description: 'Audit Auspex Two-Tree topology, stable IDs, parent refs, and projection readiness'
---

## Follow-up Questions

Use `vscode_askQuestions` for all follow-up questions instead of freeform chat prompts.

# lens-auspex-map-audit

Run the shared prompt-start sync first:

```bash
uv run --script lens.core/_bmad/lens-work/skills/lens-preflight/scripts/light-preflight.py --caller lens-auspex-map-audit
```

If preflight exits non-zero, stop and surface the failure.

Then load and follow `lens.core/_bmad/lens-work/skills/lens-auspex-map-audit/SKILL.md`.

Use this as the preferred audit route for organic topology work before relying on a derived map or promoting feature knowledge into ledgers.

