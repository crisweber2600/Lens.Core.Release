# Init Feature Flow

Initialize a new feature with 2-branch topology in the control repo, feature.yaml, governance index entry, and track-aware planning PR behavior.

## Outcome

After this flow completes:

- Branches `{featureId}` and `{featureId}-plan` exist in the control repo
- Parent governance markers exist at `features/{domain}/domain.yaml` and `features/{domain}/{service}/service.yaml` when they were previously missing
- `feature.yaml` exists at `{governance-repo}/features/{domain}/{service}/{featureId}/feature.yaml` on `main`
- `feature-index.yaml` on `main` has a new entry for `{featureId}`
- `summary.md` stub exists at `{governance-repo}/features/{domain}/{service}/{featureId}/summary.md` on `main`
- All governance artifacts are committed directly to `main` — the governance repo never leaves `main`
- A PR exists from `{featureId}-plan` → `{featureId}` titled "Planning: {feature name}" when the selected track creates a planning PR immediately
- For the `express` track, the plan branch is created but the planning PR is deferred until planning artifacts exist

## Process

### Step 1: Gather Inputs

Prompt for (if not already provided):

1. **Feature name** — human-readable, used to derive the short `featureSlug` (e.g., "Auth Token Refresh" → `auth-refresh`)
2. **Domain** — organizational domain (e.g., `platform`, `commerce`)
3. **Service** — service within the domain (e.g., `identity`, `payments`)
4. **Track** — read the `tracks` keys from `lifecycle.yaml`, present those lifecycle track choices explicitly, and require the user to choose one before creation. If `{default_track}` exists and is present in `lifecycle.yaml`, label it as the preferred track only; do not apply it without explicit confirmation. Do not offer stale aliases such as `quickplan` when they are absent from `lifecycle.yaml`.

Derive:

- **featureSlug** — slugify the feature name: lowercase, replace spaces with `-`, strip non-alphanumeric
- **featureId** — canonical `{normalized-domain}-{normalized-service}-{featureSlug}` (e.g., `platform-identity-auth-refresh`)
- **username** — from `{username}` resolved on activation

**Before proceeding, present the derived identity to the user as read-only context:**

```
Derived featureId:
  Feature Slug:  {featureSlug}
  Feature ID:    {domain}-{service}-{featureSlug}
```

Set `featureSlug` to the slug portion only. Set `featureId` to the canonical full value. Do not ask the user to approve, shorten, or customize `featureId`; only the track selection remains an explicit user choice before proceeding.

### Step 2: Validate with Dry Run

```bash
python3 ./scripts/init-feature-ops.py create \
  --governance-repo {governance_repo} \
  --control-repo {control_repo} \
  --feature-id {featureId} \
  --domain {domain} \
  --service {service} \
  --name "{feature name}" \
  --track {track} \
  --username {username} \
  --execute-governance-git \
  --dry-run
```

If validation fails, report the error and prompt for correction. Do not proceed until validation passes.

### Step 3: Create Files and Get Git Commands

```bash
python3 ./scripts/init-feature-ops.py create \
  --governance-repo {governance_repo} \
  --control-repo {control_repo} \
  --feature-id {featureId} \
  --domain {domain} \
  --service {service} \
  --name "{feature name}" \
  --track {track} \
  --username {username} \
  --execute-governance-git
```

The script:

1. Creates parent governance markers at `features/{domain}/domain.yaml` and `features/{domain}/{service}/service.yaml` when they are missing
2. Creates `feature.yaml` at `{governance-repo}/features/{domain}/{service}/{featureId}/feature.yaml`
3. Adds an entry to `{governance-repo}/feature-index.yaml` (creates if absent)
4. Creates `{governance-repo}/features/{domain}/{service}/{featureId}/summary.md` stub
5. Executes governance checkout/pull/add/commit/push directly on `main`
6. Returns `featureSlug`, `governance_git_commands`, `control_repo_git_commands`, `control_repo_activation_commands`, `remaining_git_commands`, `remaining_commands`, `governance_git_executed`, and `governance_commit_sha`, plus `gh_commands`, plus `planning_pr_created`, `starting_phase`, `recommended_command`, and `router_command` so the handoff matches `lifecycle.yaml`

### Step 4: Execute Git and GitHub Commands

When `--execute-governance-git` succeeds, the script has already published governance artifacts on `main`. Execute the returned `remaining_commands` in order, then the `gh_commands` when present. Do not rewrite the returned branch-creation step into raw `git checkout -b` commands; the generated git-orchestration command anchors the feature topology to the control repo's default branch, and the activation step switches to `{featureId}-plan` while updating local Lens context.

```bash
# Each command in remaining_commands runs in order
# Example remaining commands after governance auto-publish:
# uv run --script {project-root}/lens.core/_bmad/lens-work/skills/lens-git-orchestration/scripts/git-orchestration-ops.py \
#   create-feature-branches \
#   --governance-repo {governance_repo} \
#   --repo {control_repo} \
#   --feature-id {featureId}
# uv run --script {project-root}/lens.core/_bmad/lens-work/skills/lens-switch/scripts/switch-ops.py \
#   switch \
#   --governance-repo {governance_repo} \
#   --feature-id {featureId} \
#   --control-repo {control_repo} \
#   --personal-folder {personal_output_folder}

# Then gh_commands when `planning_pr_created == true`
# (PR is in the control repo, not governance):
# gh pr create --repo {control_repo} --head {featureId}-plan --base {featureId} ...
```

> **Note:** The governance repo stays on `main` throughout — no feature branches are created there. The 2-branch topology (`{featureId}` + `{featureId}-plan`) exists only in the control repo and should be created through git-orchestration so `{featureId}` starts from the repo default branch.

> **Auto-publish note:** `create`, `create-domain`, and `create-service` can be run with `--execute-governance-git`. In that mode the script performs the governance checkout/pull/add/commit/push itself, auto-commits local governance changes that are already on `main`, and callers should surface only the returned `remaining_commands` for any manual follow-up.

> **Failure note:** If governance git preflight or execution fails, stop and surface the error. Do not fall back to a manual governance publish recipe.

### Step 5: Confirm Initialization

Present the initialization summary to the user:

| Field | Value |
|-------|-------|
| Feature ID | `{featureId}` |
| Feature Slug | `{featureSlug}` |
| Start Phase | `{starting_phase}` |
| Next Step | `/next` or `{recommended_command}` |
| Feature Branch | `{featureId}` (control repo) |
| Plan Branch | `{featureId}-plan` (control repo) |
| Domain Marker | `features/{domain}/domain.yaml` ✓ |
| Service Marker | `features/{domain}/{service}/service.yaml` ✓ |
| Feature YAML | `features/{domain}/{service}/{featureId}/feature.yaml` (governance `main`) |
| PR | Immediate planning PR for non-`express` tracks; deferred for `express` until planning artifacts exist |
| Index | `feature-index.yaml` (governance `main`) ✓ |
| Summary | `features/{domain}/{service}/{featureId}/summary.md` (governance `main`) ✓ |

Offer to run **Auto-Context Pull** to load domain context before handing off to planning, then route into the lifecycle-aware next step with `/next` or the returned `{recommended_command}`.
