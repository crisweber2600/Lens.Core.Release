---
mode: ask
---

# lens-switch

FIRST, run the preflight gate from the workspace root:

```bash
uv run --script lens.core/_bmad/lens-work/skills/lens-preflight/scripts/light-preflight.py
```

If that command exits non-zero, stop and surface the failure. Do not proceed.

ONLY AFTER a successful prompt-start sync, load and follow the module prompt at
`lens.core/_bmad/lens-work/prompts/lens-switch.prompt.md`.

When presenting a feature list, use `vscode_askQuestions` if available to ask the user to select.
If `vscode_askQuestions` is not available, render the numbered menu and STOP.
