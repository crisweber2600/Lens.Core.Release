---
description: 'Create Auspex read-only stakeholder reporting snapshots'
---

## Follow-up Questions

Use `vscode_askQuestions` for all follow-up questions instead of freeform chat prompts.

# lens-auspex-reporting-snapshot

Run the shared prompt-start sync first:

```bash
uv run --script lens.core/_bmad/lens-work/skills/lens-preflight/scripts/light-preflight.py --caller lens-auspex-reporting-snapshot
```

If preflight exits non-zero, stop and surface the failure.

Then load and follow `lens.core/_bmad/lens-work/skills/lens-auspex-reporting-snapshot/SKILL.md`.

Snapshots are generated views for stakeholders and future UI ingestion. They are not source truth.

