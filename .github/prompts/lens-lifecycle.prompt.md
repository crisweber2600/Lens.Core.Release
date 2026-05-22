---
agent: agent
---

# lens-lifecycle

FIRST, run the preflight gate from the workspace root:

```bash
uv run --script lens.core/_bmad/lens-work/skills/lens-preflight/scripts/light-preflight.py --caller lens-lifecycle
```

If that command exits non-zero, stop and surface the failure. Do not proceed.

ONLY AFTER a successful prompt-start sync, load and follow the module prompt at
`lens.core/_bmad/lens-work/prompts/lens-lifecycle.prompt.md`.

Use `vscode_askQuestions` if follow-up input is needed.