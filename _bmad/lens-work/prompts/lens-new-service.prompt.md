---
description: lens new-service release prompt
mode: agent
---

# /new-service

Load `_bmad/lens-work/skills/bmad-lens-init-feature/SKILL.md` and execute intent `create-service`.

Runtime config to resolve before invocation:
- governance_repo
- target_projects_path (optional)
- output_folder (optional)
- personal_output_folder (required)

The user wants to initialize a new service container, not a feature. The flow must:
1. Resolve or ask for the parent domain when not supplied by active context
2. Ask for the service display name
3. Derive a safe service slug using the same normalization pattern as `new-domain`
4. Confirm the slug with edit/cancel options before invoking the script
5. Create `{governance_repo}/features/{domain}/{service}/service.yaml`
6. Create `{governance_repo}/constitutions/{domain}/{service}/constitution.md`
7. If the parent domain marker or constitution is absent, create them first by calling `create-domain` helpers — do not re-implement domain creation inline
8. Pass `--target-projects-root {target_projects_path}` when configured
9. Pass `--docs-root {output_folder}` when configured
10. Pass `--personal-folder {personal_output_folder}` so `context.yaml` is written with the active domain and service
11. Pass `--execute-governance-git` so governance `main` is pulled, written, committed, and pushed by the script
12. Do not create feature branches, feature.yaml, summary.md, feature-index entries, or lifecycle artifacts

Report `governance_commit_sha` when present. Surface `remaining_git_commands` only for manual workspace scaffold follow-up. Do not implement service writes in this prompt; delegate to the skill script.
