# Switch Feature

Switch the active feature context to a different feature and load appropriate cross-feature context.

## When to Use

- When the user says "switch to feature X", "work on X", "context switch to X", or similar
- When starting work on a different feature in the same session
- When an agent needs to load context for a feature other than the current one

## Resolution Order

1. Validate `--feature-id` exists in `feature-index.yaml`
2. Read full state from `feature.yaml`
3. Compute cross-feature context to load based on dependency types
4. Return feature state and context paths; set active feature in session

If the feature is not found in `feature-index.yaml`, return an error immediately — do not fall through to filesystem search.

## Process

Run the switch operation:

```bash
uv run --script {project-root}/{release_repo_root}/_bmad/lens-work/skills/lens-switch/scripts/switch-ops.py \
  switch \
  --governance-repo {governance_repo} \
  --feature-id {target_feature_id} \
  --control-repo {control_repo}
```

If `{personal_output_folder}` is known, pass `--personal-folder {personal_output_folder}`. When `--personal-folder` is omitted and `--control-repo` is provided, the script defaults local context to `{control_repo}/.lens/personal/context.yaml`.

The entry prompt owns numbered-menu interaction. Do not guess a target feature from branch names or open files when the user has not explicitly chosen one.

## Output

```json
{
  "status": "pass",
  "plan_branch": "auth-login-plan",
  "branch_switched": true,
  "feature": {
    "id": "auth-login",
    "name": "User Authentication",
    "domain": "platform",
    "service": "identity",
    "phase": "dev",
    "track": "quickplan",
    "priority": "high",
    "status": "active",
    "owner": "cweber",
    "stale": false,
    "updated": "2026-03-15T10:00:00Z"
  },
  "context_to_load": {
    "summaries": ["/path/to/governance/features/platform/identity/user-profile/summary.md"],
    "full_docs": ["/path/to/governance/features/platform/auth/oauth-provider/tech-plan.md"]
  }
}
```

`stale: true` is set when `updated` is more than 30 days old. `context_to_load.summaries` contains paths for `related` dependencies. `context_to_load.full_docs` contains paths for `depends_on` and `blocks` dependencies.

`plan_branch` is always `{featureId}-plan`. `branch_switched: true` means the control repo was checked out to that branch. `branch_switched: false` with a `branch_error` means the checkout failed — typically the branch does not exist yet; run `/new-feature` to initialize it.

## Branch Checkout

After running the switch command:

- If `branch_switched: true` — confirm with: `[{featureId}] active. Branch: {plan_branch}.`
- If `branch_switched: false` — include a warning: `⚠ Could not checkout {plan_branch}: {branch_error}. Run /new-feature to create the feature branches.`
- If `--control-repo` is omitted, the script defaults to `.` and attempts the checkout in the workspace root.

## Stale Context Warning

When `stale: true` is returned, surface a warning inline with the switch confirmation:

```
[auth-login] active. Phase: dev.
⚠ Context may be stale (last updated 45 days ago).
```

Do not block the switch — load context and proceed; only warn.

## Cross-Feature Context Loading

After a successful switch, load the files listed in `context_to_load`:

| Relationship type | Files to load | Why |
|---|---|---|
| `related` | `summary.md` | Lightweight awareness; full docs unnecessary |
| `depends_on` | `tech-plan.md` | Active dependency; need full technical spec |
| `blocks` | `tech-plan.md` | Blocking dependency; need full technical spec |

Load each file using the standard file-read mechanism. Files that don't exist on disk can be skipped with a warning — they may not yet be authored.

## Session State

After a successful switch:
1. Set `session.active_feature_id = feature.id`
2. Store `session.active_feature = feature` (the full feature object from output)
3. Store `session.cross_feature_context = context_to_load` (the paths loaded)

Subsequent skill invocations should read `session.active_feature_id` without calling this script again.

## Errors

| Error | Exit code | Cause |
|-------|-----------|-------|
| `Feature '{id}' not found in feature-index.yaml` | 1 | featureId not in index |
| `feature-index.yaml not found at {path}` | 1 | Index file missing from governance repo |
| `feature.yaml not found for '{id}'` | 1 | Index entry exists but feature.yaml is absent |
| `Invalid feature-id: ...` | 1 | featureId contains invalid characters or path traversal |
| `Failed to parse feature-index.yaml: ...` | 1 | YAML parse error in index |
