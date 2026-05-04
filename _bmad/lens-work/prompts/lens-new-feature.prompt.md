---
description: 'Feature initializer entry controller'
---

# lens-new-feature

Use this prompt as the entry controller for `/lens-new-feature`. It must delegate to the `lens-init-feature` skill and must not create governance files, branches, or feature records inline.

## Prompt-Start Sync

Before reading config or invoking `init-feature-ops.py`:

1. Check whether this invocation already includes a successful run of `uv run ./lens.core/_bmad/lens-work/skills/lens-preflight/scripts/light-preflight.py` from the workspace root.
2. If not, run `uv run ./lens.core/_bmad/lens-work/skills/lens-preflight/scripts/light-preflight.py` now from the workspace root.
3. If that command exits non-zero, stop and surface the failure.
4. Do not resolve config paths, read governance state, or execute `init-feature-ops.py` until the shared prompt-start sync has succeeded.

## Exact Paths

- Module config: `{project-root}/lens.core/_bmad/lens-work/bmadconfig.yaml`
- Optional governance override: `{project-root}/.lens/governance-setup.yaml`
- Discover skill: `{project-root}/lens.core/_bmad/lens-work/skills/lens-discover/SKILL.md`
- Discover script: `{project-root}/lens.core/_bmad/lens-work/skills/lens-discover/scripts/discover-ops.py`
- Init-feature skill: `{project-root}/lens.core/_bmad/lens-work/skills/lens-init-feature/SKILL.md`
- Init-feature script: `{project-root}/lens.core/_bmad/lens-work/skills/lens-init-feature/scripts/init-feature-ops.py`

## Resolution Rules

1. Attempt to read `{project-root}/lens.core/_bmad/lens-work/bmadconfig.yaml`. If it exists, resolve:
   - `{release_repo_root}` from `release_repo_root` (default: `lens.core`)
   - `{governance_repo}` from `governance_repo_path`
   - `{target_projects_path}` from `target_projects_path`
   - `{control_repo}` from control repo context (default: `{project-root}`)
   - `{personal_output_folder}` from `personal_output_folder`
2. If `{project-root}/.lens/governance-setup.yaml` exists and contains `governance_repo_path`, prefer that value over `bmadconfig.yaml`.
3. If `{governance_repo}` remains unset, stop with `config_missing` and tell the user: `Run /lens-new-domain or /lens-new-service to configure governance first.`
4. If non-governance values remain unset, use these defaults:
   - `{release_repo_root}` = `lens.core`
   - `{target_projects_path}` = `{project-root}/TargetProjects`
   - `{control_repo}` = `{project-root}`
   - `{personal_output_folder}` = `{project-root}/.lens/personal`
5. Do not search the workspace for alternate config files or script locations.

## Repo Inventory Sync

Before invoking `init-feature-ops.py create`, automatically run the discover workflow in headless mode so repositories cloned after `/new-service` are reflected in governance inventory:

1. Load `{project-root}/{release_repo_root}/_bmad/lens-work/skills/lens-discover/SKILL.md`.
2. Execute discover with `--headless` against `{governance_repo}/repo-inventory.yaml` and `{target_projects_path}`.
3. Newly registered inventory entries must keep `feature_base_branch` blank. Do not ask for, infer, or set a PR base branch during `/new-feature`; that decision belongs to PR creation time.
4. If discover fails, stop and surface the discover failure before feature creation.

## Execution

1. After the repo inventory sync succeeds, load `{project-root}/{release_repo_root}/_bmad/lens-work/skills/lens-init-feature/SKILL.md`.
2. Execute the skill intent `create` for a new feature.
3. If `init-feature-ops.py` does not expose the `create` subcommand in this installed version, stop with:

```text
not_yet_implemented: `/lens-new-feature` requires the `init-feature-ops.py create` subcommand. The prompt is published, but the runtime create implementation must be restored by the lens-dev-new-codebase-new-feature dev phase before this command can create features.
```

4. When the `create` subcommand is available, the skill must perform the progressive-disclosure flow from `lens-init-feature`, including explicit track selection before any write. The derived canonical featureId is read-only; display it for transparency but do not ask the user to approve, shorten, or customize it.

## Scope Boundaries

- Do not create or edit files in `.github/prompts/`; IDE adapter mirroring is a human-owned post-dev action.
- Do not write governance files directly from this prompt; all writes must be delegated to `init-feature-ops.py` or the relevant Lens governance skill.
- Do not infer a feature name, domain, service, or track from branches or open files without user confirmation.
