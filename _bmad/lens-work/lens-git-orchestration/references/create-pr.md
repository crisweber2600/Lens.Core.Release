# create-pr

## Outcome

An open PR exists between two named branches. If a matching open PR already exists, it is reused instead of creating a duplicate. Auto-merge can be requested when GitHub policy allows it.

## Preconditions

- Both `--base` and `--head` branches exist locally or on `origin`
- `gh` CLI is installed and authenticated
- The repo has a configured GitHub remote

## Process

1. Check for an existing open PR for `--head` → `--base`
2. If one exists, return its URL and current auto-merge state
3. Otherwise run `gh pr create --base <base> --head <head> --title <title> --body <body>`
4. If `--auto-merge` was requested, run `gh pr merge <pr-url> --auto --merge`
5. Return the PR URL, whether it was newly created, and whether auto-merge is enabled

## Output

```json
{
  "strategy": "pr",
  "base_branch": "main",
  "head_branch": "payments-auth",
  "pr_url": "https://github.com/org/repo/pull/84",
  "created": true,
  "auto_merge_requested": false,
  "auto_merge_enabled": false,
  "dry_run": false
}
```