# create-feature-branches

## Outcome

`{featureId}` and `{featureId}-plan` branches exist, are pushed to the remote with tracking refs set up, and are ready for work.

## Preconditions

- `feature.yaml` exists for `{featureId}` in the governance repo (validate via `find_feature_yaml`)
- Neither `{featureId}` nor `{featureId}-plan` already exists locally or on remote
- Working directory is clean (no uncommitted changes in the repo)
- `{featureId}` is slug-safe: lowercase alphanumeric + hyphens only, no slashes, no leading/trailing hyphens

## Process

1. Run `validate_feature_id(featureId)` — reject if not slug-safe
2. Run `find_feature_yaml(governance_repo, featureId)` — reject if not found
3. Run `branch_exists(repo, featureId)` — reject if already exists
4. Run `branch_exists(repo, f"{featureId}-plan")` — reject if already exists
5. Resolve `{default_branch}` from the explicit argument when provided, otherwise from the repo's remote default branch (fallback: `main`)
6. `git checkout {default_branch} && git pull origin {default_branch}`
7. `git checkout -b {featureId}`
8. `git push --set-upstream origin {featureId}`
9. `git checkout -b {featureId}-plan`
10. `git push --set-upstream origin {featureId}-plan`
11. Return to `{default_branch}` (leave repo in a neutral state)

## Output

```json
{
  "feature_id": "payments-auth-oauth",
  "base_branch": "payments-auth-oauth",
  "plan_branch": "payments-auth-oauth-plan",
  "base_remote": "origin/payments-auth-oauth",
  "plan_remote": "origin/payments-auth-oauth-plan",
  "created_from": "main"
}
```

## Error Cases

| Condition | Error |
|-----------|-------|
| `feature.yaml` not found | `"feature_yaml_not_found"` |
| Base branch already exists | `"branch_already_exists": "{featureId}"` |
| Plan branch already exists | `"branch_already_exists": "{featureId}-plan"` |
| Invalid feature ID | `"invalid_feature_id": "{featureId}"` |
| Git push fails | `"push_failed"` with git stderr |
