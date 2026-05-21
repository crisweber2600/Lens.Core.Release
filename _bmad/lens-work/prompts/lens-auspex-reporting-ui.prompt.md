---
description: 'Maintain the Auspex MVP1 reporting UI contract and snapshot data shape'
---

## Follow-up Questions

Use `vscode_askQuestions` for all follow-up questions instead of freeform chat prompts.

# lens-auspex-reporting-ui

Run the shared prompt-start sync first:

```bash
uv run --script lens.core/_bmad/lens-work/skills/lens-preflight/scripts/light-preflight.py --caller lens-auspex-reporting-ui
```

If preflight exits non-zero, stop and surface the failure.

Then load and follow `lens.core/_bmad/lens-work/skills/lens-auspex-reporting-ui/SKILL.md`.

This command owns the Lens-side read-only MVP1 reporting UI contract. It does not create a deployable UI app in this repo.

