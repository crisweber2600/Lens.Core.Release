---
description: lens new-domain release prompt
mode: agent
---

# /new-domain

Load `_bmad/lens-work/skills/bmad-lens-init-feature/SKILL.md` and execute intent `create-domain`.

Runtime config to resolve before invocation:
- governance_repo
- target_projects_path
- output_folder
- personal_output_folder (required)

The user wants to initialize a new domain, not a feature. The flow must:
1. Create `{governance_repo}/features/{domain}/domain.yaml`
2. Create `{governance_repo}/constitutions/{domain}/constitution.md`
3. Pass `--target-projects-root {target_projects_path}` when configured
4. Pass `--docs-root {output_folder}` when configured
5. Pass `--personal-folder {personal_output_folder}` so `context.yaml` becomes active for the new domain with `service: null`
6. Pass `--execute-governance-git` so governance `main` is pulled, written, committed, and pushed by the script
7. Do not create feature branches, feature.yaml, or lifecycle artifacts

Report `governance_commit_sha` when present. Surface `remaining_git_commands` only for manual workspace scaffold follow-up. Do not implement domain writes in this prompt; delegate to the skill script.
