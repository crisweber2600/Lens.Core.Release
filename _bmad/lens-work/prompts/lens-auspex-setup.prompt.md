---
description: 'Configure Auspex as the preferred Lens topology and reporting workflow'
---

## Follow-up Questions

Use `vscode_askQuestions` for all follow-up questions instead of freeform chat prompts.

# lens-auspex-setup

Run the shared prompt-start sync first:

```bash
uv run --script lens.core/_bmad/lens-work/skills/lens-preflight/scripts/light-preflight.py --caller lens-auspex-setup
```

If preflight exits non-zero, stop and surface the failure.

Then load and follow `lens.core/_bmad/lens-work/skills/lens-auspex-setup/SKILL.md`.

This command configures the imported Auspex module surface and help metadata as the preferred Lens workflow for Two-Tree topology, derived maps, living ledgers, Salmon impact, audits, and stakeholder reporting. It must not remove or disable legacy domain, service, or feature commands.

