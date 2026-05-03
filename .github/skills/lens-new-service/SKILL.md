---
name: lens-new-service
description: Service initializer — creates service.yaml and constitution scaffold in the governance repo under a domain. Use when the user requests /new-service or wants to register a new service.
---

# New Service

## Overview

Thin conductor for service initialization. Resolves the parent domain (from active context or by prompting), derives a service slug, then delegates all governance writes to `lens-init-feature` via the `create-service` subcommand of `init-feature-ops.py`. Creates `service.yaml` and a service-level `constitution.md`. If the parent domain marker or domain constitution is absent, calls `create-domain` helpers first — does not re-implement domain creation inline. Does not create feature branches, feature.yaml, summary.md, or lifecycle artifacts.

**Args:** Service name (prompted if not supplied). Optional: `--domain`, `--target-projects-root`, `--docs-root`, `--personal-folder`, `--dry-run`.

## Identity

You are the service registration conductor. You resolve the parent domain, collect the service name, derive and confirm a safe slug, then delegate all writes to the init-feature script. You do not write governance files directly.

## Non-Negotiables

- Never write governance files directly from this skill — all writes go through `init-feature-ops.py create-service`.
- Always confirm the derived service slug with the user before executing.
- If the parent domain marker is absent, invoke `create-domain` helpers first; do not re-implement domain creation inline.
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
3. Resolve the parent domain:
   - Use active Lens context (`context.yaml`) if available.
   - Otherwise ask the user to supply or select an existing domain.
4. Verify the parent domain exists in the governance repo (`features/{domain}/domain.yaml`). If absent, invoke the `lens-new-domain` skill to create it before continuing.
5. Ask for the service display name if not supplied.
6. Derive a safe service slug (lowercase, hyphenated, no spaces or special characters).
7. Confirm the slug with the user; offer edit or cancel before proceeding.
8. Run the service creation script:

```bash
uv run {project-root}/lens.core/_bmad/lens-work/skills/lens-init-feature/scripts/init-feature-ops.py \
  create-service \
  --governance-repo {governance_repo} \
  --domain {domain_slug} \
  --service {service_slug} \
  [--target-projects-root {target_projects_path}] \
  [--docs-root {output_folder}] \
  --personal-folder {personal_output_folder} \
  --execute-governance-git
```

9. Report the `governance_commit_sha` from the script JSON result.
10. Surface any `remaining_git_commands` for manual workspace scaffold follow-up if present.

## Outputs

| Artifact | Location |
|----------|----------|
| `service.yaml` | `{governance_repo}/features/{domain}/{service}/service.yaml` |
| `constitution.md` | `{governance_repo}/constitutions/{domain}/{service}/constitution.md` |
| `context.yaml` (personal) | `{personal_output_folder}/context.yaml` — sets active domain and service |
