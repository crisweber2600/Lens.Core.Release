---
description: lens new-service release prompt
mode: agent
---

# /new-service

Load `{project-root}/lens.core/_bmad/lens-work/skills/lens-init-feature/SKILL.md` and execute intent `create-service`.

Runtime config to resolve before invocation:
- governance_repo
- target_projects_path (optional)
- output_folder (optional)
- personal_output_folder (required)

The user wants to initialize a new service container, not a feature. The flow must:
1. Use `vscode_askQuestions` for follow-up questions when available.
2. If the parent domain must be selected and `vscode_askQuestions` is unavailable, render a numbered menu and STOP.
3. Resolve or ask for the parent domain when not supplied by active context.
4. Ask for the service display name.
5. Derive a safe service slug using the same normalization pattern as `new-domain`.
6. Proceed without a confirmation stop when the derived slug is valid. Only ask for a manual slug when normalization yields an invalid safe ID.
7. Create `{governance_repo}/features/{domain}/{service}/service.yaml`.
8. Create `{governance_repo}/constitutions/{domain}/{service}/constitution.md`.
9. If the parent domain marker or constitution is absent, create them first by calling `create-domain` helpers — do not re-implement domain creation inline.
10. Pass `--target-projects-root {target_projects_path}` when configured.
11. Pass `--docs-root {output_folder}` when configured.
12. Pass `--personal-folder {personal_output_folder}` so `context.yaml` is written with the active domain and service.
13. Pass `--execute-governance-git` so governance `main` is pulled, written, committed, and pushed by the script.
14. Do not create feature branches, feature.yaml, summary.md, feature-index entries, or lifecycle artifacts.
15. After successful service creation, instruct the user to clone any related service repositories into `TargetProjects/{domain}/{service}/{repo-name}` before running `/new-feature`.

Report `governance_commit_sha` when present. Surface `related_service_clone_guidance` before the `/new-feature` handoff. Surface `remaining_git_commands` only for manual workspace scaffold follow-up. Do not implement service writes in this prompt; delegate to the skill script.
