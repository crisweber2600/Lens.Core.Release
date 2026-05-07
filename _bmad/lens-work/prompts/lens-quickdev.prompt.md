---
description: 'Governed QuickDev wrapper for dev-ready Lens features.'
---

# /lens-quickdev

FIRST, run the preflight gate from the workspace root:

```bash
uv run --script lens.core/_bmad/lens-work/skills/lens-preflight/scripts/light-preflight.py --caller lens-quickdev
```

If that command exits non-zero, stop and surface the failure. Do not proceed.

ONLY AFTER a successful prompt-start sync, load and follow the module skill at
`lens.core/_bmad/lens-work/skills/lens-quickdev/SKILL.md`.

When asked for user input, use `vscode_askQuestions` if available.
If `vscode_askQuestions` is not available, render the numbered menu and STOP.

This prompt is only a redirect. Do not add prompt-local business logic.