---
description: 'Feature completion entry controller'
---

# lens-complete

Use this prompt as the entry controller for `/lens-complete`. It must delegate lifecycle completion behavior to `lens-complete` and must not implement archive or governance writes inline.

## Prompt-Start Sync

Before reading config or invoking `complete-ops.py`:

1. Check whether this invocation already includes a successful run of `uv run ./lens.core/_bmad/lens-work/skills/lens-preflight/scripts/light-preflight.py` from the workspace root.
2. If not, run that command now from the workspace root.
3. If that command exits non-zero, stop and surface the failure.
4. Do not resolve config paths, read governance state, or execute completion operations until the shared prompt-start sync has succeeded.

## Exact Paths

- Module config: `{project-root}/lens.core/_bmad/lens-work/bmadconfig.yaml`
- Optional governance override: `{project-root}/.lens/governance-setup.yaml`
- Complete skill: `{project-root}/lens.core/_bmad/lens-work/skills/lens-complete/SKILL.md`
- Complete script: `{project-root}/lens.core/_bmad/lens-work/skills/lens-complete/scripts/complete-ops.py`

## Resolution Rules

1. Attempt to read `{project-root}/lens.core/_bmad/lens-work/bmadconfig.yaml`. If it exists, resolve:
   - `{release_repo_root}` from `release_repo_root` (default: `lens.core`)
   - `{governance_repo}` from `governance_repo_path`
   - `{control_repo}` from control repo context (default: `{project-root}`)
2. If `{project-root}/.lens/governance-setup.yaml` exists and contains `governance_repo_path`, prefer that value over `bmadconfig.yaml`.
3. If `{governance_repo}` remains unset, stop with `config_missing` and tell the user: `Run /lens-new-domain or /lens-new-service to configure governance first.`
4. Do not search the workspace for alternate config files or script locations.

## Execution

1. Load `{project-root}/{release_repo_root}/_bmad/lens-work/skills/lens-complete/SKILL.md`.
2. Determine the requested operation:
   - `check-preconditions`
   - `finalize`
   - `archive-status`
3. If the user did not provide an operation, default to `check-preconditions`.
4. If `complete-ops.py` is absent in this installed version, stop with:

```text
not_yet_implemented: `/lens-complete` has a published command contract, but `complete-ops.py` is not implemented yet. Runtime completion operations are owned by the lens-dev-new-codebase-complete dev phase.
```

5. When `complete-ops.py` is available, invoke the operation exactly as described by `lens-complete/SKILL.md` and surface its structured JSON result.

## Scope Boundaries

- Do not create or edit files in `.github/prompts/`; IDE adapter mirroring is a human-owned post-dev action.
- Do not write `feature.yaml`, `feature-index.yaml`, or `summary.md` directly from this prompt.
- `finalize` is irreversible and must require the explicit confirmation gate defined in `lens-complete/SKILL.md`.
