# merge-plan

## Outcome

In legacy `3-branch`, planning artifacts from `{featureId}-plan` are integrated into `{featureId}` via PR or direct merge. In `flat`, this command returns a structured no-op because planning artifacts already live on the control repo default branch.

## Merge Strategies

| Strategy | When to Use | Mechanism |
|----------|-------------|-----------|
| `pr` (default) | Team review required | Creates GitHub PR: `{featureId}-plan` → `{featureId}` |
| `direct` | Solo or automated merge | `git merge --no-ff` locally, then push |
| `flat` topology | Plan merge not required | Returns `no_op: true` |

## Preconditions

- In `3-branch`, both `{featureId}` and `{featureId}-plan` exist
- In `flat`, the control repo default branch exists
- Working directory is clean on the branch being merged from
- For `pr` strategy: `gh` CLI is authenticated

## Process — PR strategy

1. Confirm required topology branches exist
2. Reuse an existing open PR for `{featureId}-plan` → `{featureId}` when one already exists; otherwise run `gh pr create --base {featureId} --head {featureId}-plan --title "[plan] {featureId} — merge planning artifacts" --body "Auto-created by lens-git-orchestration"`
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
  "control_topology": "flat",
  "strategy": "pr",
  "default_branch": "main",
  "base_branch": "main",
  "plan_branch": "main",
  "no_op": true,
  "auto_merge_requested": true,
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
