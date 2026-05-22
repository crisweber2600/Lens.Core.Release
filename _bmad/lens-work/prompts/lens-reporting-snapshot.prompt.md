---
description: 'Create Lens reporting snapshots'
---

# lens-reporting-snapshot

Use this prompt as the entry controller for `/lens-reporting-snapshot`.

## Prompt-Start Sync

Before loading the skill, make sure this invocation has completed prompt-start sync. If it has not, run this command from the workspace root:

```bash
uv run --script lens.core/_bmad/lens-work/skills/lens-preflight/scripts/light-preflight.py --caller lens-reporting-snapshot
```

If that command exits non-zero, stop and surface the failure.

## Execution

Load and follow `{project-root}/lens.core/_bmad/lens-work/skills/lens-reporting-snapshot/SKILL.md` exactly. Use `vscode_askQuestions` for follow-up questions when user input is required.