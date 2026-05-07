# create-pr

## Outcome

An open PR exists between two named branches. If a matching open PR already exists, it is reused instead of creating a duplicate. Auto-merge can be requested when GitHub policy allows it.

## Preconditions

- Both `--base` and `--head` branches exist locally or on `origin`
- For repos under `TargetProjects/`, governance `repo-inventory.yaml` has a matching entry with `feature_base_branch`
- `gh` CLI is installed and authenticated
- The repo has a configured GitHub remote

## Process

1. For TargetProjects repos, resolve `base_branch` from `repo-inventory.yaml` `feature_base_branch`. If the field is missing, ask the user which branch PRs should merge into and update the inventory entry before retrying.
2. Check for an existing open PR for `--head` → `base_branch`
3. If one exists, return its URL and current auto-merge state
4. Otherwise run `gh pr create --base <base_branch> --head <head> --title <title> --body <body>`
5. If `--auto-merge` was requested, run `gh pr merge <pr-url> --auto --merge`
6. Return the PR URL, whether it was newly created, and whether auto-merge is enabled

## Output

```json
{
  "strategy": "pr",
  "base_branch": "develop",
  "base_branch_source": "repo-inventory.feature_base_branch",
  "head_branch": "payments-auth",
  "pr_url": "https://github.com/org/repo/pull/84",
  "created": true,
  "auto_merge_requested": false,
  "auto_merge_enabled": false,
  "dry_run": false
}
```