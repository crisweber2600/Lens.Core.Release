# Move Feature

Relocates a feature to a new domain/service by moving its directory, updating its `feature.yaml`, updating `feature-index.yaml`, and patching references in dependent features. Interactive — requires explicit user confirmation before executing.

## When to Use

- When a feature has been placed in the wrong domain or service
- When domain/service restructuring requires relocating features
- Never invoke automatically — always present the plan and wait for confirmation

## Pre-Flight Validation

Before showing the move plan, run `validate` to check all preconditions:

```bash
uv run scripts/move-feature-ops.py validate \
  --governance-repo {governance_repo} \
  --feature-id {featureId} \
  --target-domain {targetDomain} \
  --target-service {targetService}
```

**Validate output:**

```json
{
  "status": "pass",
  "feature_id": "auth-login",
  "from": { "domain": "platform", "service": "identity" },
  "to": { "domain": "core", "service": "sso" },
  "blockers": [],
  "dependent_features": ["user-portal", "admin-dashboard"]
}
```

If `status` is `"fail"`, surface the `blockers` to the user and stop. Do not proceed.

**Blocker examples:**

| Blocker | Action |
|---------|--------|
| Feature has in-progress or done stories | Inform user: dev work is committed — move blocked until stories are removed or feature is complete |
| Target path already exists | Inform user: another feature is already at that location |
| Feature not found | Inform user: verify featureId and try again |

## Presenting the Move Plan

Use the `from` and `to` fields from validate output to build the confirmation display:

```
Moving: features/{from.domain}/{from.service}/{featureId}
    →   features/{to.domain}/{to.service}/{featureId}

Updates required:
  • feature.yaml: domain: {from.domain} → {to.domain}, service: {from.service} → {to.service}
  • feature-index.yaml: 1 entry
  • {N} dependent feature(s) with references to patch: {dependent_features.join(", ")}

Proceed? (yes/no)
```

If `dependent_features` is empty, omit the dependent features line.

## Execution Steps

On user confirmation, execute in order:

### Step 1 — Move directory

```bash
uv run scripts/move-feature-ops.py move \
  --governance-repo {governance_repo} \
  --feature-id {featureId} \
  --target-domain {targetDomain} \
  --target-service {targetService}
```

**Move output:**

```json
{
  "status": "pass",
  "old_path": "features/platform/identity/auth-login",
  "new_path": "features/core/sso/auth-login",
  "index_updated": true,
  "files_moved": 7
}
```

If `status` is `"fail"`, stop and report the error. The directory has not been moved — no cleanup needed.

### Step 2 — Patch references in dependent features

Run only if `dependent_features` was non-empty in the validate output:

```bash
uv run scripts/move-feature-ops.py patch-references \
  --governance-repo {governance_repo} \
  --feature-id {featureId} \
  --old-path {move_result.old_path} \
  --new-path {move_result.new_path}
```

See `./references/notify-dependents.md` for details.

## Post-Move Summary

After successful execution, present:

```
✓ Moved: features/platform/identity/auth-login → features/core/sso/auth-login
✓ feature.yaml updated: domain=core, service=sso
✓ feature-index.yaml updated
✓ {N} file(s) patched in {M} dependent feature(s)

Next: commit these changes to main via git-state skill.
```

## Dry Run

Use `--dry-run` to preview without executing:

```bash
uv run scripts/move-feature-ops.py move \
  --governance-repo {governance_repo} \
  --feature-id {featureId} \
  --target-domain {targetDomain} \
  --target-service {targetService} \
  --dry-run
```

Dry-run output has `"dry_run": true` — no files are moved.

## Error Handling

If any step fails after the directory has already been moved (Step 1 succeeded, Step 2 failed), report the partial state explicitly:

```
⚠ Directory moved successfully, but reference patching failed: {error}
Manual action required: run patch-references manually or restore from git.
```

Never silently swallow a partial failure.
