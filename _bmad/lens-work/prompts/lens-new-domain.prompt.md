---
description: 'Domain initializer entry controller'
---

# lens-new-domain

Use this prompt as the entry controller for `/lens-new-domain`. It must delegate to the `lens-new-domain` skill and must not create governance files or inspect candidate repo paths inline.

## Prompt-Start Sync

Before reading config or invoking `init-feature-ops.py`:

1. Check whether this invocation already includes a successful run of `uv run ./lens.core/_bmad/lens-work/skills/lens-preflight/scripts/light-preflight.py` from the workspace root.
2. If not, run `uv run ./lens.core/_bmad/lens-work/skills/lens-preflight/scripts/light-preflight.py` now from the workspace root.
3. If that command exits non-zero, stop and surface the failure.
4. Do not resolve config paths, inspect governance repo state, or execute `init-feature-ops.py` until the shared prompt-start sync has succeeded.

## Exact Paths

- Module config: `{project-root}/lens.core/_bmad/lens-work/bmadconfig.yaml`
- Optional governance override: `{project-root}/.lens/governance-setup.yaml`
- New-domain skill: `{project-root}/lens.core/_bmad/lens-work/skills/lens-new-domain/SKILL.md`
- Init-feature script: `{project-root}/lens.core/_bmad/lens-work/skills/lens-init-feature/scripts/init-feature-ops.py`

## Resolution Rules

1. Attempt to read `{project-root}/lens.core/_bmad/lens-work/bmadconfig.yaml`. If it exists, resolve:
	- `{release_repo_root}` from `release_repo_root` (default: `lens.core`)
	- `{governance_repo}` from `governance_repo_path`
	- `{target_projects_path}` from `target_projects_path` (default: `{project-root}/TargetProjects`)
	- `{output_folder}` from `output_folder` (default: `{project-root}/docs`)
	- `{personal_output_folder}` from `personal_output_folder` (default: `{project-root}/.lens/personal`)
2. If `{project-root}/.lens/governance-setup.yaml` exists and contains `governance_repo_path`, prefer that value over `bmadconfig.yaml`.
3. If `{governance_repo}` remains unset, stop with `config_missing` and tell the user: `Set .lens/governance-setup.yaml or governance_repo_path in bmadconfig.yaml before running /lens-new-domain.`
4. Do not search the workspace for alternate config files or script locations.
5. Do not probe alternate governance repo candidates with `ls`, `git log`, `git branch`, or `git config`; either use the resolved config value or stop with a config error.

## Execution

1. Load `{project-root}/{release_repo_root}/_bmad/lens-work/skills/lens-new-domain/SKILL.md`.
2. Execute the skill flow for domain creation.
3. The skill must collect the display name, derive and confirm a slug, and delegate all writes to `init-feature-ops.py create-domain`.
4. The skill must pass `--target-projects-root {target_projects_path}`, `--docs-root {output_folder}`, `--personal-folder {personal_output_folder}`, and `--execute-governance-git`.
5. On success, report `governance_commit_sha` when present and surface only `remaining_git_commands` for manual workspace scaffold follow-up.

## Scope Boundaries

- Do not write governance files directly from this prompt.
- Do not create feature branches, feature.yaml, summary.md, feature-index entries, or lifecycle artifacts.
- Do not inspect alternate repo candidates inline; config resolution is deterministic.
