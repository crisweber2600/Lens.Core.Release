mode: agent
description: "Initialize a new service within a domain"

Load and follow the skill at: `lens.core/_bmad/lens-work/skills/bmad-lens-init-feature/SKILL.md`

The user wants to initialize a new **service** — not a feature. This means:
1. Create the service marker at `{governance_repo}/features/{domain}/{service}/service.yaml` (and parent `domain.yaml` if absent)
2. Create a service-level `constitution.md` at `{governance_repo}/constitutions/{domain}/{service}/constitution.md` inheriting from the domain constitution (create domain constitution too if absent)
3. If `{target_projects_path}` is configured, scaffold `{target_projects_path}/{domain}/{service}/` by passing `--target-projects-root {target_projects_path}` to the `create-service` subcommand
4. If `{output_folder}` is configured, scaffold `{output_folder}/{domain}/{service}/` by passing `--docs-root {output_folder}` to the `create-service` subcommand
5. Pass `--personal-folder {personal_output_folder}` to the `create-service` subcommand so that `context.yaml` is written to the personal folder with the new domain and service as the active context
6. Do NOT create feature branches or feature.yaml — service initialization is governance-only

Use the `create-service` subcommand of `skills/bmad-lens-init-feature/scripts/init-feature-ops.py` with `--execute-governance-git`.
Report governance git success, include the returned `governance_commit_sha` when present, and only surface any `remaining_git_commands` for manual workspace scaffold follow-up.
