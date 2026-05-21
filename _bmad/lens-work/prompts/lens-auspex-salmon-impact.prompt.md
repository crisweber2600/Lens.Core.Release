---
description: 'Review Auspex Salmon upstream-impact signals and recursive consistency risk'
---

## Follow-up Questions

Use `vscode_askQuestions` for all follow-up questions instead of freeform chat prompts.

# lens-auspex-salmon-impact

Run the shared prompt-start sync first:

```bash
uv run --script lens.core/_bmad/lens-work/skills/lens-preflight/scripts/light-preflight.py --caller lens-auspex-salmon-impact
```

If preflight exits non-zero, stop and surface the failure.

Then load and follow `lens.core/_bmad/lens-work/skills/lens-auspex-salmon-impact/SKILL.md`.

Use this command when feature work discovers upstream impact that may affect service, domain, program, sibling feature, or ledger assumptions.

