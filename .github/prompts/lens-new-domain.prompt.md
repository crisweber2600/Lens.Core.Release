---
agent: agent
---

FIRST, run the preflight gate from the workspace root:

```bash
uv run _bmad/lens-work/skills/lens-preflight/scripts/light-preflight.py --caller lens-new-domain
```

If that command exits non-zero, stop and surface the failure. Do not proceed.

ONLY AFTER a successful prompt-start sync, load and follow the module prompt at
`lens.core/_bmad/lens-work/prompts/lens-new-domain.prompt.md`.

When asked for user input, use `vscode_askQuestions` if available.
If `vscode_askQuestions` is not available, render the numbered menu and STOP.
