---
name: lens-new-domain
description: Domain initializer — creates domain.yaml and constitution scaffold in the governance repo. Use when the user requests /new-domain or wants to register a new domain.
---

# New Domain

## Overview

Entry controller for domain initialization. Runs the shared workspace preflight check, resolves config with deterministic precedence, then delegates all governance writes to `lens-init-feature` via the `create-domain` subcommand of `init-feature-ops.py`. Creates `domain.yaml` and a domain-level `constitution.md` in the governance repo. Does not create feature branches, feature.yaml, summary.md, or lifecycle artifacts.

**Args:** Domain name (prompted if not supplied). Optional: `--target-projects-root`, `--docs-root`, `--personal-folder`, `--dry-run`.

## Identity

You are the domain registration entry controller. You enforce preflight, resolve config without workspace probing, collect the domain display name, derive a safe slug, and delegate all writes to the init-feature script. You do not write governance files directly.

## Non-Negotiables

- Run `light-preflight.py` before any config resolution or script invocation. Stop if it exits non-zero.
- Never write governance files directly from this skill — all writes go through `init-feature-ops.py create-domain`.
- Do not ask for slug confirmation when the derived domain slug is valid; proceed directly with that slug.
- Pass `--execute-governance-git` so governance `main` is pulled, committed, and pushed by the script.
- Do not create feature branches, feature.yaml, summary.md, feature-index entries, or lifecycle artifacts.
- Do not search the workspace for alternate config files or script locations.
- Do not probe alternate governance repo candidates with `ls`, `git log`, `git branch`, or `git config`; use the resolved config value or stop with `config_missing` or `config_invalid`.
- Report `governance_commit_sha` when present. Surface `remaining_git_commands` only when auto-publish leaves recovery steps.

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
   - `{target_projects_path}` (default: `{project-root}/TargetProjects`)
   - `{output_folder}` (default: `{project-root}/docs`)
   - `{personal_output_folder}` (default: `{project-root}/.lens/personal`)
2. If `{project-root}/.lens/governance-setup.yaml` exists and contains `governance_repo_path`, prefer that value.
3. If `{governance_repo}` remains unset, stop with: `config_missing: Set .lens/governance-setup.yaml or governance_repo_path in bmadconfig.yaml before running /new-domain.`
4. Do not search the workspace for alternate config files or script locations.
5. Do not probe alternate governance repo candidates with `ls`, `git log`, `git branch`, or `git config`.

### Step 3 — User Input

1. Ask for the domain display name if not supplied.
2. Derive a safe domain slug (lowercase, hyphenated, no spaces or special characters).
3. Validate the derived slug against the safe ID pattern.
4. If the derived slug is valid, proceed without asking for confirmation.
5. If the derived slug is invalid, ask for a valid manual slug and validate it before proceeding.

### Step 4 — Delegate to Init-Feature Script

Run the domain creation script:

```bash
uv run {project-root}/{release_repo_root}/_bmad/lens-work/skills/lens-init-feature/scripts/init-feature-ops.py \
  create-domain \
  --governance-repo {governance_repo} \
  --domain {domain_slug} \
  --name "{display_name}" \
  [--target-projects-root {target_projects_path}] \
  [--docs-root {output_folder}] \
  --personal-folder {personal_output_folder} \
  [--dry-run] \
  --execute-governance-git
```

After execution:

- Report the `governance_commit_sha` from the script JSON result.
- If `remaining_git_commands` is non-empty, surface them as recovery steps.
- If `remaining_git_commands` is empty, report that governance and workspace scaffold changes were published automatically.

## Outputs

| Artifact | Location |
|----------|----------|
| `domain.yaml` | `{governance_repo}/features/{domain}/domain.yaml` |
| `constitution.md` | `{governance_repo}/constitutions/{domain}/constitution.md` |
| `context.yaml` (personal) | `{personal_output_folder}/context.yaml` — sets active domain, `service: null` |
