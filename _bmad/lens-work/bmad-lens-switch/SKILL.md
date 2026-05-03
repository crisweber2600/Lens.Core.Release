---
name: bmad-lens-switch
description: Feature context switcher. Use when switching the active feature context, loading cross-feature context for a new feature, or listing available features to switch to.
---

# Feature Context Switcher

## Overview

This skill manages the active feature context for a Lens agent session. It switches the working context to a different feature, loads cross-feature context appropriate to the relationship type, and confirms the new active feature. Feature listing always reads from `feature-index.yaml` — no branch switching. **When no `feature-index.yaml` exists yet, listing falls back to a domain/service inventory scanned from `domain.yaml` and `service.yaml` files in the governance repo's `features/` directory.**

**The non-negotiable:** Switching context never modifies any feature.yaml or governance state. It only changes which feature is active in the agent session and loads the relevant supporting context.

**Args:** Accepts operation as first argument: `switch`, `list`. Pass `--feature-id <id>` to target a specific feature.

## Identity

You manage active feature context for the Lens agent session. You switch the working context to a different feature, load cross-feature context appropriate to the relationship type, and confirm the new active feature. Feature listing is always from `main` — never branch switching. You validate that the target feature exists before switching, surface stale context warnings, and load supporting context (summaries for related features, full docs for depends_on/blocks). When switching context, you are concise. When listing, you present a clean table.

## Communication Style

- Confirm a context switch with one line — e.g., `[auth-login] active. Phase: dev.` — never more than two lines for a normal switch
- Show new feature status immediately after switching: phase, priority, stale warning if applicable
- Surface stale context warnings inline: `⚠ Context may be stale (last updated 45 days ago)`
- Present feature lists as tables with id, domain, service, phase, status, and owner
- If the target feature is not found, give the exact error and suggest running `list` to see available features

## Principles

- **main-first** — feature list always reads `feature-index.yaml` from the governance repo; never requires or performs branch switching; falls back to domain/service inventory when no index exists yet
- **context-aware** — load summaries for `related` features, full docs for `depends_on` and `blocks` features; never over-load context
- **session-state** — the active feature persists across skill invocations within the session; confirm switches explicitly
- **validation-first** — always validate featureId exists in feature-index.yaml before attempting to load feature.yaml
- **stale-aware** — compute and surface staleness from the `updated` timestamp in feature.yaml; threshold is 30 days

## Vocabulary

| Term | Definition |
|------|-----------|
| **active feature** | The currently focused feature in the agent session; set by `switch` and persists until changed |
| **cross-feature context** | Supporting context loaded for related or dependent features — summaries for `related`, full docs for `depends_on`/`blocks` |
| **session context** | In-memory state tracking the active featureId and loaded context for this session |
| **feature-index.yaml** | Index file at `{governance_repo}/feature-index.yaml` listing all features with id, domain, service, status, owner, summary — authoritative source for listing |
| **feature.yaml** | Per-feature YAML at `features/{domain}/{service}/{featureId}/feature.yaml` — full lifecycle state |
| **stale context** | Feature whose `updated` timestamp is more than 30 days old |
| **governance repo** | The repository containing shared Lens configuration and feature data; resolved from config as `{governance_repo}` |

## On Activation

Load available config from `{project-root}/lens.core/_bmad/lens-work/bmadconfig.yaml`. If `{project-root}/.lens/governance-setup.yaml` exists and contains `governance_repo_path`, prefer that override for the governance repo. Resolve:

- `{release_repo_root}` (default: `lens.core`) — release payload root used for anchored script paths
- `{governance_repo}` (default: `{project-root}/TargetProjects/lens/lens-governance`) — governance repo root path
- `{control_repo}` (default: `{project-root}`) — control repo root path; used for git branch checkout on switch
- `{personal_output_folder}` (default: `{project-root}/.lens/personal`) — local session context location

Missing config is normal. Do not search the workspace for alternate config files or script copies. The session active feature is not set until an explicit `switch` is performed.

## Capabilities

| Capability | Route |
| ---------- | ----- |
| Switch Feature | Load `./references/switch-feature.md` |
| List Features | Load `./references/list-features.md` |
| Numbered Menu | When invoked with no `--feature-id`, run List then present a numbered menu and wait for the user's exact selection |

### Numbered Menu Flow

When `lens-switch` is invoked without a target feature (no `--feature-id` argument), default to the numbered menu:

1. Run `switch-ops.py list` to get features with `num` fields (1-indexed)
2. If the result returns `mode: domains`, present the inventory and stop — no feature switch is possible yet
3. If the result returns `mode: features`, render the numbered list (see `list-features.md` for format)
4. Prompt: `Enter a number to switch, or q to cancel:`
5. If a question tool is available, use it; otherwise STOP and wait for the user's next reply
6. On valid number input: resolve the feature id at that position and run `switch-ops.py switch --feature-id <id>`
7. Confirm switch with one line — e.g., `[auth-login] active. Phase: dev.`
8. On `q`: cancel cleanly with no changes
9. On invalid input: rerender the same menu and STOP again

Never infer a target feature from the current branch, open files, or recent paths. The entry prompt owns menu state and must wait for the user's explicit selection.

## Script Reference

`./scripts/switch-ops.py` — Python script (uv-runnable) with three subcommands:

```bash
# List available features (non-archived by default)
uv run --script {project-root}/{release_repo_root}/_bmad/lens-work/skills/bmad-lens-switch/scripts/switch-ops.py \
  list \
  --governance-repo {governance_repo}

# List all features including archived
uv run --script {project-root}/{release_repo_root}/_bmad/lens-work/skills/bmad-lens-switch/scripts/switch-ops.py \
  list \
  --governance-repo {governance_repo} \
  --status-filter all

# Validate and prepare context for switching to a feature
uv run --script {project-root}/{release_repo_root}/_bmad/lens-work/skills/bmad-lens-switch/scripts/switch-ops.py \
  switch \
  --governance-repo {governance_repo} \
  --feature-id auth-login \
  --control-repo {control_repo} \
  --personal-folder {personal_output_folder}

# Get file paths for cross-feature context
uv run --script {project-root}/{release_repo_root}/_bmad/lens-work/skills/bmad-lens-switch/scripts/switch-ops.py \
  context-paths \
  --governance-repo {governance_repo} \
  --feature-id auth-login \
  --domain platform \
  --service identity
```

The `switch` result always includes `plan_branch` (`{featureId}-plan`). It also includes `branch_switched: true|false`, `checked_out_branch`, and `branch_error`, using `.` as the default control-repo root when `--control-repo` is omitted.

## JSON Contracts

### List Success - Features Mode

Returned when `feature-index.yaml` exists and contains feature records.

```json
{
  "status": "pass",
  "mode": "features",
  "features": [
    {
      "num": 1,
      "id": "auth-login",
      "domain": "platform",
      "service": "identity",
      "status": "active",
      "owner": "cweber",
      "summary": "User authentication flow",
      "target_repo": {
        "repo": "lens.core.src",
        "working_branch": "feature/auth-login",
        "dev_branch_mode": "feature-id",
        "pr_state": null
      }
    }
  ],
  "total": 1
}
```

Fields:

- `num` is 1-based and stable within the returned list.
- `target_repo` is null when no target repo metadata exists; otherwise it contains `repo`, `working_branch`, `dev_branch_mode`, `pr_state`, and compatibility fields.

### List Success - Domains Mode

Returned when `feature-index.yaml` does not exist. This is an orientation view only; no feature should be selected from it.

```json
{
  "status": "pass",
  "mode": "domains",
  "domains": [
    {
      "id": "platform",
      "name": "Platform",
      "domain": "platform",
      "status": "active",
      "owner": "cweber",
      "services": []
    }
  ],
  "total_domains": 1,
  "total_services": 0,
  "message": "No features initialized yet. Showing domain/service inventory from governance repo."
}
```

### Switch Success

Returned after a target feature id validates against `feature-index.yaml`, `feature.yaml` loads, local context is written, and branch checkout is attempted.

```json
{
  "status": "pass",
  "feature_id": "auth-login",
  "domain": "platform",
  "service": "identity",
  "phase": "dev",
  "track": "quickplan",
  "priority": "high",
  "owner": "cweber",
  "stale": false,
  "context_path": "/repo/features/platform/identity/auth-login",
  "personal_context_path": "/control/.lens/personal/context.yaml",
  "target_repo_state": {
    "repo": "lens.core.src",
    "working_branch": "feature/auth-login",
    "dev_branch_mode": "feature-id",
    "pr_state": null
  },
  "context_paths": {
    "related": [{"id": "user-profile", "path": "/gov/features/platform/identity/user-profile/summary.md", "exists": true}],
    "depends_on": [{"id": "oauth-provider", "path": "/control/docs/platform/auth/oauth-provider/tech-plan.md", "exists": false}],
    "blocks": []
  },
  "branch_switched": true,
  "checked_out_branch": "auth-login-plan",
  "branch_error": null
}
```

Semantics:

- `stale` is true only when `feature.yaml.updated` is more than 30 days old. It is a warning, not a blocker.
- `context_path` points to the governance feature directory. `personal_context_path` points to the local context file written by switch.
- `target_repo_state` is null when `target_repos` is empty.
- `context_paths.*[].exists` tells callers whether to load the file. Missing paths remain in the response with `exists: false`.
- `branch_switched` reports checkout success. `checked_out_branch` is null when checkout fails. `branch_error` is null on success, `branch_not_found` for a missing `{featureId}-plan` branch, or raw git stderr for other checkout errors.

### Switch Failure

```json
{
  "status": "fail",
  "error": "feature_not_found",
  "message": "Feature 'missing-feature' not found in feature-index.yaml"
}
```

Known error codes: `invalid_feature_id`, `invalid_domain`, `invalid_service`, `config_missing`, `config_malformed`, `index_not_found`, `index_malformed`, `feature_not_found`, `feature_yaml_not_found`, `feature_yaml_malformed`, `context_write_failed`.

## Focused Regression

Run from the target source repo root:

```bash
uv run --with pytest {project-root}/lens.core/_bmad/lens-work/skills/bmad-lens-switch/scripts/tests/test-switch-ops.py -q
```

## Integration Points

| Skill | How switch is used |
|-------|-------------------|
| New Feature flow | Sets the initial active feature after feature creation |
| `bmad-lens-quickplan` | Uses active feature as the planning target |
| All feature-context skills | Read active featureId from session context set by this skill |
