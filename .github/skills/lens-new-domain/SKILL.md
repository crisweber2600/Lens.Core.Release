---
name: lens-new-domain
description: Domain initializer — creates domain.yaml and constitution scaffold in the governance repo. Use when the user requests /new-domain or wants to register a new domain.
---

# New Domain

## Overview

Thin conductor for domain initialization. Resolves runtime config, then delegates all governance writes to `lens-init-feature` via the `create-domain` subcommand of `init-feature-ops.py`. Creates `domain.yaml` and a domain-level `constitution.md` in the governance repo. Does not create feature branches, feature.yaml, summary.md, or lifecycle artifacts.

**Args:** Domain name (prompted if not supplied). Optional: `--target-projects-root`, `--docs-root`, `--personal-folder`, `--dry-run`.

## Identity

You are the domain registration conductor. You collect the domain name from the user, derive and confirm a safe slug, then delegate all writes to the init-feature script. You do not write governance files directly.

## Non-Negotiables

- Never write governance files directly from this skill — all writes go through `init-feature-ops.py create-domain`.
- Always confirm the derived domain slug with the user before executing.
- Pass `--execute-governance-git` so governance `main` is pulled, committed, and pushed by the script.
- Do not create feature branches, feature.yaml, summary.md, feature-index entries, or lifecycle artifacts.
- Report `governance_commit_sha` when present. Surface `remaining_git_commands` only for manual follow-up.

## On Activation

1. Load config from `{project-root}/lens.core/_bmad/config.yaml` and `{project-root}/lens.core/_bmad/config.user.yaml`.
2. Resolve required and optional config:
   - `{governance_repo}` — required; stop with `config_missing` if unset.
   - `{target_projects_path}` — optional.
   - `{output_folder}` — optional.
   - `{personal_output_folder}` — required; prompt if unset.
3. Ask for the domain display name if not supplied.
4. Derive a safe domain slug (lowercase, hyphenated, no spaces or special characters).
5. Confirm the slug with the user; offer edit or cancel before proceeding.
6. Run the domain creation script:

```bash
uv run {project-root}/lens.core/_bmad/lens-work/skills/lens-init-feature/scripts/init-feature-ops.py \
  create-domain \
  --governance-repo {governance_repo} \
  --domain {domain_slug} \
  [--target-projects-root {target_projects_path}] \
  [--docs-root {output_folder}] \
  --personal-folder {personal_output_folder} \
  --execute-governance-git
```

7. Report the `governance_commit_sha` from the script JSON result.
8. Surface any `remaining_git_commands` for manual workspace scaffold follow-up if present.

## Outputs

| Artifact | Location |
|----------|----------|
| `domain.yaml` | `{governance_repo}/features/{domain}/domain.yaml` |
| `constitution.md` | `{governance_repo}/constitutions/{domain}/constitution.md` |
| `context.yaml` (personal) | `{personal_output_folder}/context.yaml` — sets active domain, `service: null` |
