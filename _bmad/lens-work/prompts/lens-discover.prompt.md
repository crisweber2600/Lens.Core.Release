---
description: 'Discover local target repos and sync governance inventory'
---

# lens-discover

Use this prompt as the entry controller for `/lens-discover`. Resolve config first, then delegate to the discover skill.

## Prompt-Start Sync

Before reading config or invoking discover:

1. Confirm the `.github/prompts/lens-discover.prompt.md` stub already ran `uv run --script ./lens.core/_bmad/lens-work/scripts/light-preflight.py` successfully from the workspace root.
2. If not, run that command now from the workspace root.
3. If that command exits non-zero, stop and surface the failure.

## Config Resolution

Resolve paths in this order:

1. If `{project-root}/.lens/governance-setup.yaml` exists and contains `governance_repo_path`, use it.
2. Otherwise read `{project-root}/lens.core/_bmad/lens-work/bmadconfig.yaml` and use `governance_repo_path`.
3. Resolve `target_projects_path` from config when present, otherwise use `{project-root}/TargetProjects`.

If governance config is missing, stop and tell the user to run Lens onboarding or domain/service setup before discover.

## Delegation

After config is resolved, read and follow:

`lens.core/_bmad/lens-work/skills/lens-discover/SKILL.md`

Pass through user arguments such as `--headless`, `-H`, or `--dry-run` to the skill behavior.