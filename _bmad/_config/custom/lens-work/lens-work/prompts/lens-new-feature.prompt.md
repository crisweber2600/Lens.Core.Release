mode: agent
description: "Initialize a new feature with 2-branch topology, feature YAML, and PR"

Load and follow the skill at: `lens.core/_bmad/lens-work/skills/bmad-lens-init-feature/SKILL.md`

The user wants to initialize a new **feature**. This means:
1. Create a 2-branch topology (`{featureId}` and `{featureId}-plan`) in the control repo
2. Commit `feature.yaml` to governance `main` under `features/{domain}/{service}/{featureId}/feature.yaml`
3. Register the feature in `feature-index.yaml` on `main`
4. Create a `summary.md` stub on `main` under `features/{domain}/{service}/{featureId}/summary.md`
5. For non-`express` tracks: open a PR from the plan branch to the feature branch in the control repo
6. For `express` track: defer the planning PR until planning artifacts exist on the plan branch
7. After creation, report the returned `starting_phase` and recommend `/next` or the returned `recommended_command`; never hardcode `/quickplan`

Apply progressive disclosure — ask only for feature name, domain, and service upfront; derive featureId and validate against `feature-index.yaml`; then require the user to choose a track explicitly before writing anything.

Use the `create` subcommand of `skills/bmad-lens-init-feature/scripts/init-feature-ops.py` with `--execute-governance-git`.
When `{personal_output_folder}` is configured, pass `--personal-folder {personal_output_folder}` so the returned activation step writes `context.yaml` to the correct local Lens folder.
Report governance git success, include the returned `governance_commit_sha` when present, and only surface any `remaining_commands` plus `gh_commands` for manual follow-up.
Execute the returned `remaining_commands` in order exactly as provided. Do not replace the returned branch-creation step with manual `git checkout -b` commands, because it resolves the control repo default branch before creating `{featureId}` and `{featureId}-plan`. The returned activation step then switches the control repo to `{featureId}-plan` and makes the new feature the active Lens context.
If governance git preflight or execution fails, stop and surface the error; do not provide a manual governance git recipe.
