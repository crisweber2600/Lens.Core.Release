# commit-artifacts

## Outcome

One or more files are staged and committed to the current branch with a structured, audit-friendly commit message. Optionally pushed to remote immediately.

## Commit Message Format

```
[{PHASE}] {featureId} — {description}
```

**Phase tokens** (from feature.yaml `phase` field):
`preplan` | `plan` | `dev` | `review` | `done`

**Examples:**
```
[preplan] payments-auth-oauth — product brief draft
[plan] payments-auth-oauth — architecture document complete
[dev] payments-auth-oauth — implementation milestone 1
```

## Preconditions

- Branch is `{featureId}` or `{featureId}-plan` (or `{featureId}-dev-{username}`)
- All specified file paths exist relative to the repo root
- At least one file is specified

## Process

1. Verify current branch matches the expected branch for this feature
2. Resolve phase from `feature.yaml` if not explicitly provided
3. Print the files that will be staged — request confirmation (unless `--no-confirm`)
4. `git add {file_paths}`
5. `git commit -m "[{phase}] {featureId} — {description}"`
6. If `--push`: immediately `git push`
7. Return commit SHA and message

## Output

```json
{
  "feature_id": "payments-auth-oauth",
  "branch": "payments-auth-oauth-plan",
  "phase": "plan",
  "files_committed": ["docs/prd.md", "docs/arch.md"],
  "commit_sha": "abc1234",
  "commit_message": "[plan] payments-auth-oauth — architecture document complete",
  "pushed": false
}
```

## Error Cases

| Condition | Error |
|-----------|-------|
| No files specified | `"no_files_specified"` |
| File does not exist | `"file_not_found": "{path}"` |
| Nothing to commit (files already staged and identical) | `"nothing_to_commit"` |
| Push fails | `"push_failed"` with git stderr |
