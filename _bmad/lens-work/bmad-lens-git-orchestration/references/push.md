# push

## Outcome

The current branch (or a named branch) is pushed to the remote. Tracking ref is set if not already configured.

## Preconditions

- At least one unpushed local commit exists (warns but does not fail if already up-to-date)
- Remote `origin` is configured

## Process

1. If `{branch}` not specified: use `git rev-parse --abbrev-ref HEAD`
2. Check if tracking ref exists: `git rev-parse --abbrev-ref @{u}` — if missing, use `--set-upstream`
3. `git push [--set-upstream] origin {branch}`
4. Report remote ref and the HEAD commit SHA

## Output

```json
{
  "branch": "payments-auth-oauth-plan",
  "remote": "origin/payments-auth-oauth-plan",
  "commit_sha": "abc1234",
  "tracking_set": true,
  "already_up_to_date": false
}
```

## Error Cases

| Condition | Error |
|-----------|-------|
| Remote not configured | `"remote_not_found": "origin"` |
| Push rejected (diverged) | `"push_rejected"` — instruct user to pull/rebase first |
| Auth failure | `"auth_failed"` with git stderr |
