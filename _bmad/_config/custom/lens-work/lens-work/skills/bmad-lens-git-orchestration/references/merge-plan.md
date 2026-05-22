# merge-plan

## Outcome

The planning artifacts from `{featureId}-plan` are integrated into `{featureId}` via PR or direct merge. The feature base branch now reflects the approved plan state.

## Merge Strategies

| Strategy | When to Use | Mechanism |
|----------|-------------|-----------|
| `pr` (default) | Team review required | Creates GitHub PR: `{featureId}-plan` → `{featureId}` |
| `direct` | Solo or automated merge | `git merge --no-ff` locally, then push |

## Preconditions

- Both `{featureId}` and `{featureId}-plan` exist
- Working directory is clean on the branch being merged from
- For `pr` strategy: `gh` CLI is authenticated

## Process — PR strategy

1. Confirm both branches exist
2. Reuse an existing open PR for `{featureId}-plan` → `{featureId}` when one already exists; otherwise run `gh pr create --base {featureId} --head {featureId}-plan --title "[plan] {featureId} — merge planning artifacts" --body "Auto-created by bmad-lens-git-orchestration"`
3. If `--auto-merge` was requested, run `gh pr merge <pr-url> --auto --merge` and report whether GitHub accepted auto-merge
4. Return PR URL
5. Optionally delete local `{featureId}-plan` branch after PR is merged (run on merge event or when `--delete-after-merge` flag is set)

## Process — Direct strategy

1. Confirm both branches exist and are clean
2. `git checkout {featureId}`
3. `git merge --no-ff {featureId}-plan -m "[merge] {featureId} — merge plan into base"`
4. `git push`
5. Optionally `git branch -d {featureId}-plan && git push origin --delete {featureId}-plan`

## Output

```json
{
  "feature_id": "payments-auth-oauth",
  "strategy": "pr",
  "base_branch": "payments-auth-oauth",
  "plan_branch": "payments-auth-oauth-plan",
  "pr_url": "https://github.com/org/repo/pull/42",
  "created": true,
  "auto_merge_requested": true,
  "auto_merge_enabled": true,
  "plan_branch_deleted": false
}
```

## Error Cases

| Condition | Error |
|-----------|-------|
| Base branch not found | `"base_branch_not_found"` |
| Plan branch not found | `"plan_branch_not_found"` |
| Merge conflict | `"merge_conflict"` with conflicting files |
| gh CLI not authenticated | `"gh_not_authenticated"` |
| Push fails | `"push_failed"` with git stderr |
