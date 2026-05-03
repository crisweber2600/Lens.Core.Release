---
name: lens-new-feature
description: Feature initializer entry controller — runs preflight, resolves config, then delegates to lens-init-feature for the full progressive-disclosure create flow. Use when the user requests /new-feature or wants to initialize a new Lens feature.
---

# New Feature

## Overview

Entry controller for feature initialization. Runs the shared workspace preflight check first, resolves config paths, then loads `lens-init-feature` and executes the `create` intent with full progressive disclosure — name, domain, and service upfront; track selection explicit before any write; featureId and featureSlug confirmed before execution. All governance writes are delegated to `init-feature-ops.py`. Does not create files inline.

**Args:** Feature name (prompted if not supplied). Optional: `--domain`, `--service`, `--track`, `--feature-id`.

## Identity

You are the feature initialization entry controller. You enforce the preflight gate, resolve config, then hand off to `lens-init-feature` for the create flow. You do not create governance files, branches, or feature records inline.

## Non-Negotiables

- Run `light-preflight.py` before any config resolution or script invocation. Stop if it exits non-zero.
- Never infer feature name, domain, service, or track from open files or branches without user confirmation.
- All governance writes go through `init-feature-ops.py create` — never written directly from this skill.
- Track selection is always explicit; never silently apply a default.
- FeatureId must be confirmed by the user before any write.
- Stop with `not_yet_implemented` if `init-feature-ops.py` does not expose the `create` subcommand in the installed version.

## On Activation

### Step 1 — Preflight

Run the preflight check from the workspace root:

```bash
uv run {project-root}/lens.core/_bmad/lens-work/skills/lens-preflight/scripts/light-preflight.py
```

If this exits non-zero, stop and surface the failure. Do not proceed until preflight passes.

### Step 2 — Config Resolution

1. Read `{project-root}/lens.core/_bmad/lens-work/bmadconfig.yaml`. Resolve:
   - `{release_repo_root}` (default: `lens.core`)
   - `{governance_repo}` from `governance_repo_path`
   - `{control_repo}` (default: `{project-root}`)
   - `{personal_output_folder}` (default: `{project-root}/.lens/personal`)
2. If `{project-root}/.lens/governance-setup.yaml` exists and contains `governance_repo_path`, prefer that value.
3. If `{governance_repo}` remains unset, stop with: `config_missing: Run /new-domain or /new-service to configure governance first.`

### Step 3 — Delegate to Init-Feature

1. Load `{project-root}/{release_repo_root}/_bmad/lens-work/skills/lens-init-feature/SKILL.md`.
2. Verify `init-feature-ops.py` exposes the `create` subcommand. If not, stop with:

```text
not_yet_implemented: `/new-feature` requires the `init-feature-ops.py create` subcommand.
The prompt is published but the runtime create implementation must be restored before this command can create features.
```

3. Execute the `lens-init-feature` skill with intent `create`, following its full progressive-disclosure flow:
   - Ask for feature name, domain, and service first.
   - Derive and confirm featureId and featureSlug before writing.
   - Present track choices; require explicit selection — never apply a default silently.
   - After confirmation, delegate the write to `init-feature-ops.py create`.

## Script Reference

The underlying script (owned by `lens-init-feature`):

```bash
uv run {project-root}/{release_repo_root}/_bmad/lens-work/skills/lens-init-feature/scripts/init-feature-ops.py \
  create \
  --governance-repo {governance_repo} \
  --control-repo {control_repo} \
  --feature-id {feature_id} \
  --domain {domain} \
  --service {service} \
  --name "{feature_name}" \
  --track {track} \
  --username {username} \
  --execute-governance-git
```

## Scope Boundaries

- Do not create or edit files in `.github/prompts/` — IDE adapter mirroring is a human-owned post-dev action.
- Do not write governance files directly; all writes must be delegated to `init-feature-ops.py` or a Lens governance skill.
- Do not infer name, domain, service, or track without user confirmation.
