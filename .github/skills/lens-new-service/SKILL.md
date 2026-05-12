---
name: lens-new-service
description: Service initializer — creates service.yaml and constitution scaffold in the governance repo under a domain. Use when the user requests /new-service or wants to register a new service.
---

# New Service

## Overview

Thin conductor for service initialization. Resolves the parent domain (from active context or by prompting), derives a service slug, then delegates all governance writes to `lens-init-feature` via the `create-service` subcommand of `init-feature-ops.py`. Creates `service.yaml` and a service-level `constitution.md`. If the parent domain marker or domain constitution is absent, calls `create-domain` helpers first — does not re-implement domain creation inline. Does not create feature branches, feature.yaml, summary.md, or lifecycle artifacts.

**Args:** Service name (prompted if not supplied). Optional: `--domain`, `--target-projects-root`, `--docs-root`, `--personal-folder`, `--dry-run`.

## Identity

You are the service registration conductor. You resolve the parent domain, collect the service name, derive a safe slug, and delegate all writes to the init-feature script. You do not write governance files directly.

## Non-Negotiables

- Never write governance files directly from this skill — all writes go through `init-feature-ops.py create-service`.
- Use `vscode_askQuestions` for follow-up questions when available.
- If `vscode_askQuestions` is unavailable for an explicit selection, render a numbered menu and STOP instead of freeform prompting.
- Do not ask for slug confirmation when the derived service slug is valid; proceed directly with that slug.
- If the parent domain marker is absent, invoke `create-domain` helpers first; do not re-implement domain creation inline.
- Pass `--execute-governance-git` so governance `main` is pulled, committed, and pushed by the script.
- Do not create feature branches, feature.yaml, summary.md, feature-index entries, or lifecycle artifacts.
- Report `governance_commit_sha` when present. Surface `remaining_git_commands` only for manual follow-up.
- After successful creation, instruct the user to clone any related service repositories into repo-named subfolders under `TargetProjects/{domain}/{service}` before running `/new-feature`.

## On Activation

1. Load config from `{project-root}/lens.core/_bmad/config.yaml` and `{project-root}/lens.core/_bmad/config.user.yaml`.
2. Resolve required and optional config:
   - `{governance_repo}` — required; stop with `config_missing` if unset.
   - `{target_projects_path}` — optional.
   - `{output_folder}` — optional.
   - `{personal_output_folder}` — required; prompt if unset.
3. Resolve the parent domain:
   - Use active Lens context (`context.yaml`) if available.
   - Otherwise use `vscode_askQuestions` to ask the user to supply or select an existing domain.
   - If `vscode_askQuestions` is unavailable for selection, render a numbered menu of existing domains and STOP.
4. Verify the parent domain exists in the governance repo (`features/{domain}/domain.yaml`). If absent, invoke the `lens-new-domain` skill to create it before continuing.
5. Ask for the service display name if not supplied. Use `vscode_askQuestions` when available.
6. Derive a safe service slug (lowercase, hyphenated, no spaces or special characters).
7. Validate the derived slug against the safe ID pattern.
8. If the derived slug is valid, proceed without asking for confirmation.
9. If the derived slug is invalid, ask once for a valid manual slug and validate it before proceeding.
10. Run the service creation script:

```bash
python {project-root}/lens.core/_bmad/lens-work/skills/lens-init-feature/scripts/init-feature-ops.py \
  create-service \
  --governance-repo {governance_repo} \
  --domain {domain_slug} \
  --service {service_slug} \
  [--target-projects-root {target_projects_path}] \
  [--docs-root {output_folder}] \
  --personal-folder {personal_output_folder} \
  --execute-governance-git
```

11. Report the `governance_commit_sha` from the script JSON result.
12. Surface `related_service_clone_guidance` from the script JSON result before handing off to `/new-feature`.
13. Surface any `remaining_git_commands` for manual workspace scaffold follow-up if present.

## Outputs

| Artifact | Location |
|----------|----------|
| `service.yaml` | `{governance_repo}/features/{domain}/{service}/service.yaml` |
| `constitution.md` | `{governance_repo}/constitutions/{domain}/{service}/constitution.md` |
| `context.yaml` (personal) | `{personal_output_folder}/context.yaml` — sets active domain and service |
| clone guidance | Instruct users to clone related service repositories into `TargetProjects/{domain}/{service}/{repo-name}` before `/new-feature` |
