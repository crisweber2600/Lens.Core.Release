---
description: 'Start an Auspex unit of work and hand off to the Lens lifecycle'
---

## Follow-up Questions

Use `vscode_askQuestions` for all follow-up questions instead of freeform chat prompts.

# lens-auspex-start

Run the shared prompt-start sync first:

```bash
uv run --script lens.core/_bmad/lens-work/skills/lens-preflight/scripts/light-preflight.py --caller lens-auspex-start
```

If preflight exits non-zero, stop and surface the failure.

Then load and follow `lens.core/_bmad/lens-work/skills/lens-auspex-start/SKILL.md`.

This is the preferred Auspex command for creating a new unit of work. It creates a Lens feature, bootstraps durable Auspex memory under `docs/features/<feature-id>/memory.md`, then delegates to `lens-next`.

