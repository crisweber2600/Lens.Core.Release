# create-feature-branches

## Outcome

Required topology branches exist, are pushed to the remote with tracking refs set up, and are ready for work. `flat` creates no feature-specific control branches and uses the control repo default branch; legacy `3-branch` creates `{featureId}`, `{featureId}-plan`, and `{featureId}-dev`.

## Preconditions

- `feature.yaml` exists for `{featureId}` in the governance repo (validate via `find_feature_yaml`)
- Required topology branches do not already exist locally or on remote for `3-branch`
- Working directory is clean (no uncommitted changes in the repo)
- `{featureId}` is slug-safe: lowercase alphanumeric + hyphens only, no slashes, no leading/trailing hyphens

## Process

1. Run `validate_feature_id(featureId)` — reject if not slug-safe
2. Run `find_feature_yaml(governance_repo, featureId)` — reject if not found
3. In `3-branch`, run `branch_exists(repo, featureId)` — reject if already exists
4. In `3-branch`, also reject existing `{featureId}-plan` and `{featureId}-dev`
5. Resolve `{default_branch}` from the explicit argument when provided, otherwise from the repo's remote default branch (fallback: `main`)
6. `git checkout {default_branch} && git pull origin {default_branch}`
7. In `flat`, stop here and report `no_op: true`
8. In `3-branch`, `git checkout -b {featureId}` and `git push --set-upstream origin {featureId}`
9. In `3-branch`, create and push `{featureId}-plan` and `{featureId}-dev`
10. Return to the saved branch

## Output

```json
{
  "feature_id": "payments-auth-oauth",
  "control_topology": "flat",
  "default_branch": "main",
  "base_branch": "main",
  "plan_branch": "main",
  "dev_branch": "main",
  "base_remote": "origin/main",
  "plan_remote": "origin/main",
  "created_branches": [],
  "created_from": "main",
  "no_op": true
}
```

## Error Cases

| Condition | Error |
|-----------|-------|
| `feature.yaml` not found | `"feature_yaml_not_found"` |
| Base branch already exists | `"branch_already_exists": "{featureId}"` |
| Topology branch already exists | `"branch_already_exists"` |
| Invalid feature ID | `"invalid_feature_id": "{featureId}"` |
| Git push fails | `"push_failed"` with git stderr |
