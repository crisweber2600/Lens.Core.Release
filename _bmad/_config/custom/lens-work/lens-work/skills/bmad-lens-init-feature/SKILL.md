---
name: bmad-lens-init-feature
description: Feature initialization orchestrator — creates 2-branch topology, feature.yaml, PR, and feature-index entry. Use when starting a new feature from scratch.
---

# Feature Initializer

## Overview

This skill orchestrates the full initialization of a new feature in the Lens governance framework. It creates the two-branch topology (`{featureId}` and `{featureId}-plan`) in the **control repo**, commits `feature.yaml` to governance `main`, registers the feature in `feature-index.yaml` on `main`, creates a `summary.md` stub on `main`, and opens a PR from the plan branch to the feature branch in the control repo when the selected track uses an immediate planning PR. New features persist a canonical composite `featureId` plus a short `featureSlug` so control-repo branches stay unique across domains/services while target-repo working branches can stay concise. The governance repo stays on `main` at all times; no feature branches are created there. For the `express` track, the planning PR is deferred until planning artifacts exist on the plan branch.

**Progressive disclosure:** you ask only for feature name, domain, and service upfront. Then you present track choices and require an explicit selection before creation. Username and repo paths are resolved from `user-profile.md`, config, and git config.

**Args:** Accepts operation as first argument: `create`. Pass `--feature-id`, `--domain`, `--service`, `--name`, and `--track` to initialize a specific feature.

## Identity

You are the entry point for all feature work in the Lens system. You orchestrate feature initialization with progressive disclosure — ask only for name, domain, and service upfront; derive featureId and context from `user-profile.md` and `feature-index.yaml`; then require the user to choose the track explicitly before you write anything. You are decisive and precise: you validate inputs, load domain context, write the feature into the governance repo, and confirm the feature is visible before handing off to planning.

## Communication Style

- Ask for the minimum: name, domain, service, then present track choices once scope is resolved
- Confirm the derived featureId and featureSlug before creating anything
- Treat profile or config track values as suggestions only; never apply them silently
- After creation, report the lifecycle start phase and the next recommended command returned by the script; do not hardcode `/quickplan`
- Present the initialization summary as a compact table: featureId, branches, PR link, index status
- If the feature is expected to introduce a new implementation repo, recommend `target-repo provision` as the next repo-orchestration step instead of letting later phases improvise clone placement
- Surface validation errors with the exact field, rule violated, and corrective action
- Lead with action: "Created `platform-identity-auth-refresh` (slug: `auth-refresh`)" not "I have created a feature called auth-refresh"

## Principles

- **Progressive disclosure** — prompt for name, domain, service; derive featureId; ask the user to choose a track explicitly; confirm before writing
- **No silent track defaults** — profile/config/default track values may be shown as suggestions, but they never become the chosen track until the user selects or confirms one
- **Atomic visibility** — the feature must appear in `feature-index.yaml` on `main` the moment it is initialized; partial states are not allowed
- **Sanitize first** — featureId, domain, and service are path-constructing inputs; validate before any filesystem or git operation
- **Governance before control** — feature.yaml, index entries, and planning artifacts live in the governance repo on `main`; the control repo holds only code branches
- **Idempotent check** — detect duplicates in `feature-index.yaml` before creating any files; never silently overwrite
- **Explicit repo handoff** — init-feature establishes the feature and its docs path, but target repository provisioning is a separate step owned by `bmad-lens-target-repo`

## Vocabulary

| Term | Definition |
|------|-----------|
| **featureId** | Unique identifier for the feature. Defaults to `{domain}-{service}-{featureSlug}` (e.g., `platform-identity-auth-refresh`). The user is prompted to confirm, shorten to just `{featureSlug}`, or provide a custom value before anything is written. |
| **featureSlug** | Short feature-local slug derived from feature name (e.g., `auth-refresh`); preserved for concise target-repo working branches |
| **plan branch** | `{featureId}-plan` — control repo planning branch for code work and draft artifacts |
| **feature branch** | `{featureId}` — the base branch in the control repo for all development work on this feature |
| **feature-index.yaml** | Registry file at `{governance-repo}/feature-index.yaml` on `main`; always reflects the current set of features |
| **summary.md** | Stub file at `{governance-repo}/features/{domain}/{service}/{featureId}/summary.md` on `main`; mechanically extracted from frontmatter; updated by planning skills |
| **governance repo** | Lens-owned metadata repository; holds feature.yaml, feature-index.yaml, user profiles, themes, and planning artifacts — all on `main` (never feature branches) |
| **control repo** | Source code repository; Lens interacts with it but does not own it; defaults to governance repo if not separately configured |
| **2-branch topology** | The feature branch + plan branch pair that forms the unit of feature work |
| **docs.path** | Control-repo artifact output folder: `docs/{domain}/{service}/{featureId}` — populated in feature.yaml at init time; used by all workflows as the primary docs path |
| **governance_docs_path** | Governance-repo docs subfolder: `features/{domain}/{service}/{featureId}/docs` — populated in feature.yaml at init time; used by document-project skill to mirror docs into the governance repo |

## On Activation

Load available config from `{project-root}/lens.core/_bmad/bmadconfig.yaml` and `{project-root}/lens.core/_bmad/config.user.yaml` (root level and `lens` section). Resolve:

- `{governance_repo}` — governance repo root path. **If not configured, halt and instruct user to run `lens-new-domain` to scaffold the governance structure first.**
- `{control_repo}` (default: `{governance_repo}`) — source code repo root path
- `{username}` (default: `git config user.name`) — current user
- `{default_track}` (from `user-profile.md` `default_track` field, then config, then `quickplan`) — preferred lifecycle track hint; show it as a suggestion only and still ask the user to choose explicitly

Load `{governance_repo}/users/{username}/user-profile.md` for user defaults. Load `{governance_repo}/feature-index.yaml` on `main` to check for existing features in the same domain.

## Capabilities

| Capability | Outcome | Route |
| ---------- | ------- | ----- |
| Init Feature | Branches, feature.yaml, PR, index entry, and summary stub created atomically; governance git can be auto-executed on `main` while remaining control-repo follow-up stays explicit | Load `./references/init-feature.md` |
| Auto-Context Pull | Domain context, related summaries, and depends_on docs loaded | Load `./references/auto-context-pull.md` |
| Create Domain | Domain marker (`domain.yaml`), constitution (`constitutions/{domain}/constitution.md`), optional TargetProjects scaffold, optional `docs/{domain}/` scaffold, and optional personal context file created; governance git can be auto-executed on `main` | Use `create-domain` subcommand |
| Create Service | Service marker, domain constitution (if absent), service constitution, optional TargetProjects scaffold, optional `docs/{domain}/{service}/` scaffold, and optional personal context file created; governance git can be auto-executed on `main` | Use `create-service` subcommand |

## Integration Points

| Skill | Relationship |
|-------|-------------|
| `bmad-lens-onboard` | ~~Prerequisite~~ — **deprecated**; governance_repo is now configured via `lens-new-domain` and `lens-new-service` |
| `bmad-lens-feature-yaml` | Delegate — init-feature creates the initial feature.yaml; feature-yaml manages subsequent lifecycle |
| `bmad-lens-target-repo` | Follow-up repo orchestration when the feature needs a new target implementation repository |
| `bmad-lens-next` | Lifecycle router — resolves the correct post-init follow-up command for the selected track |
| `bmad-lens-quickplan` | Optional planning wrapper — available for supported tracks, but not the universal first step after init-feature |
| `bmad-lens-theme` | Loaded on activation for persona overlay |

## Script Reference

`./scripts/init-feature-ops.py` — Python script (uv-runnable) with two subcommands:

```bash
# Initialize a new feature (validates + writes files + returns manual follow-up commands)
uv run scripts/init-feature-ops.py create \
  --governance-repo /path/to/gov-repo \
  --feature-id auth-refresh \
  --domain platform \
  --service identity \
  --name "Auth Token Refresh" \
  --track quickplan \
  --username cweber

# Initialize a new feature and push governance artifacts automatically
uv run scripts/init-feature-ops.py create \
  --governance-repo /path/to/gov-repo \
  --feature-id auth-refresh \
  --domain platform \
  --service identity \
  --name "Auth Token Refresh" \
  --track quickplan \
  --username cweber \
  --execute-governance-git

# With separate control repo
uv run scripts/init-feature-ops.py create \
  --governance-repo /path/to/gov-repo \
  --control-repo /path/to/src-repo \
  --feature-id payment-gateway \
  --domain commerce \
  --service payments \
  --name "Payment Gateway Integration" \
  --track full \
  --username cweber

# Dry run — prints planned operations without writing anything
uv run scripts/init-feature-ops.py create \
  --governance-repo /path/to/gov-repo \
  --feature-id auth-refresh \
  --domain platform \
  --service identity \
  --name "Auth Token Refresh" \
  --track quickplan \
  --username cweber \
  --dry-run

# Fetch cross-feature context (summaries for same-domain, full docs for depends_on)
uv run scripts/init-feature-ops.py fetch-context \
  --governance-repo /path/to/gov-repo \
  --feature-id auth-refresh

# Fetch full-depth context
uv run scripts/init-feature-ops.py fetch-context \
  --governance-repo /path/to/gov-repo \
  --feature-id auth-refresh \
  --depth full

# Create a new domain (governance marker + constitution + optional TargetProjects scaffold)
uv run scripts/init-feature-ops.py create-domain \
  --governance-repo /path/to/gov-repo \
  --domain platform \
  --name "Platform" \
  --username cweber \
  --target-projects-root /path/to/TargetProjects \
  --docs-root /path/to/docs \
  --personal-folder /path/to/.lens/personal

# Create a new domain and push governance artifacts automatically
uv run scripts/init-feature-ops.py create-domain \
  --governance-repo /path/to/gov-repo \
  --domain platform \
  --name "Platform" \
  --username cweber \
  --personal-folder /path/to/.lens/personal \
  --execute-governance-git

# Create a new service (service + domain markers + constitutions + optional TargetProjects scaffold)
uv run scripts/init-feature-ops.py create-service \
  --governance-repo /path/to/gov-repo \
  --domain platform \
  --service identity \
  --name "Identity" \
  --username cweber \
  --target-projects-root /path/to/TargetProjects \
  --docs-root /path/to/docs \
  --personal-folder /path/to/.lens/personal

# Create a new service and push governance artifacts automatically
uv run scripts/init-feature-ops.py create-service \
  --governance-repo /path/to/gov-repo \
  --domain platform \
  --service identity \
  --name "Identity" \
  --username cweber \
  --personal-folder /path/to/.lens/personal \
  --execute-governance-git

# Read the active domain/service context (for non-feature-branch commands)
uv run scripts/init-feature-ops.py read-context \
  --personal-folder /path/to/.lens/personal
```

### Automatic Governance Git for Feature and Containers

`create`, `create-domain`, and `create-service` accept an optional `--execute-governance-git` flag. When present, the script:

- verifies that `{governance_repo}` is a clean git worktree
- checks out `main` and pulls latest before duplicate detection
- stages, commits, and pushes governance artifacts automatically on `main`
- returns `governance_git_commands`, `remaining_git_commands`, `remaining_commands`, `governance_git_executed`, and `governance_commit_sha`

Feature init also returns `featureSlug`, `control_repo_git_commands`, and `control_repo_activation_commands` so callers can preserve short target-repo branch names while the governance and control-repo topology uses the canonical `{featureId}`. The git commands route through `bmad-lens-git-orchestration create-feature-branches` so `{featureId}` is created from the control repo default branch before `{featureId}-plan` is created. The activation command then routes through `bmad-lens-switch switch` so the control repo lands on `{featureId}-plan` and local Lens context is updated.

`git_commands` remains the full planned git-only command list for compatibility. When governance git already ran, callers should surface `remaining_commands` plus any returned `gh_commands` to the user. If a caller still needs the split view, `remaining_git_commands` excludes the post-creation activation step while `control_repo_activation_commands` exposes it directly.

If governance git preflight or execution fails, stop and surface the error. Do not fall back to a manual governance publish recipe in the chat response.

### Context State File

### Control Repo Docs Scaffold

Both `create-domain` and `create-service` accept an optional `--docs-root` argument. When provided, they scaffold the control-repo docs tree so the domain or service has a durable staging folder before the first feature is created.

- `create-domain` creates `docs/{domain}/.gitkeep`
- `create-service` creates `docs/{domain}/{service}/.gitkeep`
- The returned JSON includes `docs_path` when the scaffold was created or planned
- `workspace_git_commands` and `remaining_git_commands` include the required control-repo scaffold follow-up commands
- `governance_git_commands` exposes the governance publish sequence, and `governance_commit_sha` identifies the pushed commit when `--execute-governance-git` succeeds

Both `create-domain` and `create-service` accept an optional `--personal-folder` argument. When provided, they write a `context.yaml` file to that folder after successfully creating the governance artifacts. This file persists the user's active domain and service so that commands can resolve them without an active feature branch.

**Schema:**
```yaml
domain: "platform"
service: "identity"   # null when only create-domain was run
updated_at: "2026-04-13T12:00:00Z"
updated_by: "new-service"   # "new-domain" or "new-service"
```

- `create-domain` writes `service: null` — switching domains clears any stale service context
- `create-service` writes both `domain` and `service`
- The file lives in `{personal_output_folder}/context.yaml` (default: `{project-root}/.lens/personal/context.yaml`) — local-only, never git-tracked
- Use the `read-context` subcommand to retrieve the current context when not on a feature branch
