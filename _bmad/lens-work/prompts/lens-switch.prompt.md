---
description: 'Feature context switcher'
---

# lens-switch

Use this prompt as the entry controller for `/lens-switch`. Do not begin by reading the switch skill or by searching the workspace for config or script copies. Resolve the exact paths below first, then execute the appropriate switch command.

## Prompt-Start Sync

Before reading config or invoking `switch-ops.py`:

1. Check whether this `/lens-switch` invocation already includes a successful run of `uv run ./lens.core/_bmad/lens-work/scripts/light-preflight.py` from the workspace root.
2. If not, run that command now from the workspace root.
3. If that command exits non-zero, stop and surface the failure.
4. Do not resolve config paths or execute `switch-ops.py` until the shared prompt-start sync has succeeded.

## Exact Paths

- Module config: `{project-root}/lens.core/_bmad/lens-work/bmadconfig.yaml`
- Optional governance override: `{project-root}/.lens/governance-setup.yaml`
- Switch script: `{project-root}/lens.core/_bmad/lens-work/skills/lens-switch/scripts/switch-ops.py`

## Resolution Rules

1. Attempt to read `{project-root}/lens.core/_bmad/lens-work/bmadconfig.yaml`. If it exists, resolve:
    - `{release_repo_root}` from `release_repo_root` (default: `lens.core`)
    - `{governance_repo}` from `governance_repo_path`
    - `{personal_output_folder}` from `personal_output_folder`
2. If `{project-root}/.lens/governance-setup.yaml` exists and contains `governance_repo_path`, prefer that value over `bmadconfig.yaml`.
3. If `{governance_repo}` remains unset, stop with `config_missing` and tell the user: `Run /lens-onboard to set up governance config.`
4. If non-governance values remain unset, use these defaults:
    - `{release_repo_root}` = `lens.core`
    - `{control_repo}` = `{project-root}`
    - `{personal_output_folder}` = `{project-root}/.lens/personal`
5. Do not search the workspace for alternate config files or script locations.

## Execution

- If the user supplied an explicit feature id, run:

```bash
uv run --script {project-root}/{release_repo_root}/_bmad/lens-work/skills/lens-switch/scripts/switch-ops.py \
   switch \
   --governance-repo {governance_repo} \
   --feature-id {feature_id} \
   --control-repo {control_repo} \
   --personal-folder {personal_output_folder}
```

- Otherwise run:

```bash
uv run --script {project-root}/{release_repo_root}/_bmad/lens-work/skills/lens-switch/scripts/switch-ops.py \
   list \
   --governance-repo {governance_repo}
```

## Menu Control

- If the list result returns `mode: "domains"`, present the domain/service inventory and stop. Do not guess a feature.
- If the list result returns `mode: "features"` and `vscode_askQuestions` is available, ask the user to choose from the numbered options.
- If `vscode_askQuestions` is not available, render the numbered menu and STOP. Do not infer a target from the current branch, open files, recent paths, or feature status.
- When the user replies in the same conversation with a number, map it against the most recent menu you rendered.
- On `q`, cancel cleanly with no changes.
- On invalid input, rerender the same menu and STOP again.

## Successful Switch

After a successful switch:

- confirm `[feature-id] active. Phase: {phase}.`
- if `branch_switched` is false, surface the returned branch error without guessing a fallback
- if `stale` is true, surface the stale warning inline
- load only the returned `context_to_load` paths that exist on disk
- consult `lens.core/_bmad/lens-work/skills/lens-switch/SKILL.md` only if you need field semantics for the returned payload; do not load it before the first command
