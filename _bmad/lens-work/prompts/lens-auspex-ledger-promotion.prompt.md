---
description: 'Promote completed feature knowledge into Auspex living ledgers'
---

## Follow-up Questions

Use `vscode_askQuestions` for all follow-up questions instead of freeform chat prompts.

# lens-auspex-ledger-promotion

Run the shared prompt-start sync first:

```bash
uv run --script lens.core/_bmad/lens-work/skills/lens-preflight/scripts/light-preflight.py --caller lens-auspex-ledger-promotion
```

If preflight exits non-zero, stop and surface the failure.

Then load and follow `lens.core/_bmad/lens-work/skills/lens-auspex-ledger-promotion/SKILL.md`.

This command promotes feature-time knowledge into service, domain, or program ledgers without moving feature archives. Writes require explicit apply intent.

