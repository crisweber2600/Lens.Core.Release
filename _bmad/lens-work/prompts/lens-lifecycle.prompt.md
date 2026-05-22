---
description: 'Run the local Lens lifecycle engine'
---

# lens-lifecycle

Use this prompt as the entry controller for `/lens-lifecycle`.

## Prompt-Start Sync

Before loading the skill, make sure this invocation has completed prompt-start sync. If it has not, run this command from the workspace root:

```bash
uv run --script lens.core/_bmad/lens-work/skills/lens-preflight/scripts/light-preflight.py --caller lens-lifecycle
```

If that command exits non-zero, stop and surface the failure.

## Execution

Load and follow `{project-root}/lens.core/_bmad/lens-work/skills/lens-lifecycle/SKILL.md` exactly. Use `vscode_askQuestions` for follow-up questions when user input is required.