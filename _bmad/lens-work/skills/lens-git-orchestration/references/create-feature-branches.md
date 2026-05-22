# create-feature-branches

## Outcome

Required topology branches exist, are pushed to the remote with tracking refs set up, and are ready for work. `flat` creates only `{featureId}`; legacy `3-branch` creates `{featureId}`, `{featureId}-plan`, and `{featureId}-dev`.

## Preconditions

- `feature.yaml` exists for `{featureId}` in the governance repo (validate via `find_feature_yaml`)
- Required topology branches do not already exist locally or on remote
- Working directory is clean (no uncommitted changes in the repo)
- `{featureId}` is slug-safe: lowercase alphanumeric + hyphens only, no slashes, no leading/trailing hyphens

## Process

1. Run `validate_feature_id(featureId)` — reject if not slug-safe
2. Run `find_feature_yaml(governance_repo, featureId)` — reject if not found
3. Run `branch_exists(repo, featureId)` — reject if already exists
4. In `3-branch`, also reject existing `{featureId}-plan` and `{featureId}-dev`
5. Resolve `{default_branch}` from the explicit argument when provided, otherwise from the repo's remote default branch (fallback: `main`)
6. `git checkout {default_branch} && git pull origin {default_branch}`
7. `git checkout -b {featureId}`
8. `git push --set-upstream origin {featureId}`
9. In `3-branch`, create and push `{featureId}-plan` and `{featureId}-dev`
10. Return to the saved branch

## Output

```json
{
  "feature_id": "payments-auth-oauth",
  "control_topology": "flat",
  "base_branch": "payments-auth-oauth",
  "plan_branch": "payments-auth-oauth",
  "dev_branch": "payments-auth-oauth",
  "base_remote": "origin/payments-auth-oauth",
  "plan_remote": "origin/payments-auth-oauth",
  "created_branches": ["payments-auth-oauth"],
  "created_from": "main"
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
