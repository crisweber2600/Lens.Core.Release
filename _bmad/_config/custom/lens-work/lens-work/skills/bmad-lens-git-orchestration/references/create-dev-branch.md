# create-dev-branch

## Outcome

`{featureId}-dev-{username}` branch is created from the feature's base branch (`{featureId}`) and pushed to remote with tracking set up. The contributor can immediately begin work on their personal dev branch.

## Preconditions

- `{featureId}` base branch exists
- `{featureId}-dev-{username}` does NOT already exist
- `{username}` is slug-safe: lowercase alphanumeric + hyphens only

## Process

1. Validate `{username}` — reject if not slug-safe
2. Confirm `{featureId}` base branch exists (fail if not)
3. Confirm `{featureId}-dev-{username}` does not exist (fail if already present)
4. `git checkout {featureId}`
5. `git checkout -b {featureId}-dev-{username}`
6. `git push --set-upstream origin {featureId}-dev-{username}`

## Output

```json
{
  "feature_id": "payments-auth-oauth",
  "dev_branch": "payments-auth-oauth-dev-alice",
  "parent_branch": "payments-auth-oauth",
  "remote": "origin/payments-auth-oauth-dev-alice"
}
```

## Error Cases

| Condition | Error |
|-----------|-------|
| Base branch does not exist | `"base_branch_not_found": "{featureId}"` |
| Dev branch already exists | `"branch_already_exists": "{featureId}-dev-{username}"` |
| Invalid username | `"invalid_username": "{username}"` |
| Push fails | `"push_failed"` with git stderr |
