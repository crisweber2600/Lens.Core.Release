mode: agent
description: "Bootstrap a new project by creating or reusing domain/service containers, initializing a feature, and provisioning a target repo"

Load and follow the skills at: `lens.core/_bmad/lens-work/skills/bmad-lens-init-feature/SKILL.md` and `lens.core/_bmad/lens-work/skills/bmad-lens-target-repo/SKILL.md`

The user wants one guided entrypoint for a new **project stack** so they do not need to know or sequence the lower-level commands themselves. This means:
1. Ask only for the minimum upfront: the first feature name, domain, service, and whether the domain and service already exist.
2. Support both reuse and creation. If the domain already exists, skip domain creation. If the service already exists, skip service creation.
3. If the user is unsure whether the domain or service exists, inspect the governance repo before writing anything.
4. If the domain is new, use the `create-domain` subcommand of `skills/bmad-lens-init-feature/scripts/init-feature-ops.py` with `--execute-governance-git`.
5. If the service is new, use the `create-service` subcommand of `skills/bmad-lens-init-feature/scripts/init-feature-ops.py` with `--execute-governance-git`.
6. When calling `create-domain` or `create-service`, pass `--target-projects-root {target_projects_path}` when configured, `--docs-root {output_folder}` when configured, and `--personal-folder {personal_output_folder}` when configured so scaffolds and local context are created consistently.
7. Do **not** rely on the feature `create` subcommand to bootstrap a new domain or service. That path only auto-creates missing marker files; it does not replace the dedicated domain/service constitution, scaffold, or personal-context flow.
8. After the domain/service path is resolved, derive and confirm the `featureId`, require an explicit track selection, and then use the `create` subcommand of `skills/bmad-lens-init-feature/scripts/init-feature-ops.py` with `--execute-governance-git`.
9. Execute the returned branch-creation command exactly as provided; do not replace it with manual `git checkout -b` steps, because it resolves the control repo default branch before creating `{featureId}` and `{featureId}-plan`.
10. After feature creation, report the returned `starting_phase` and recommend `/next` or the returned `recommended_command`; never hardcode `/quickplan`.
11. Ask whether to provision the target repo now. Default to yes, but allow an explicit defer.
12. If repo provisioning runs, use `skills/bmad-lens-target-repo/scripts/target-repo-ops.py provision` only after feature init succeeds because repo metadata must be written into the newly created `feature.yaml`.
13. Support both repo modes in the same flow: an existing remote via `--remote-url`, or a GitHub owner plus repo name via `--owner`, `--repo-name`, and `--create-remote`.
14. Surface the canonical clone path `TargetProjects/{domain}/{service}/{repo}` before any repo write action unless the user provided a custom `--local-path`.
15. If repo provisioning runs, report the remote result, clone result, inventory update, feature metadata update, and local repo path separately so failures are easy to diagnose.
16. If the user explicitly defers repo setup, stop after feature init and recommend `/target-repo` as the next repo-orchestration step.

Apply progressive disclosure throughout the flow — do not ask the user to know or choose between `new-domain`, `new-service`, `new-feature`, or `target-repo`.

If governance git preflight or execution fails at any step, stop and surface the error; do not provide a manual governance git recipe.