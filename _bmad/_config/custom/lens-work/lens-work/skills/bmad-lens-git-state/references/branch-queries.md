# Branch Queries

## Outcome

Return detailed information about the git branches associated with a specific feature — existence, last commit, ahead/behind counts, and structure — without switching HEAD or modifying anything.

## Process

Run with the appropriate query type:

```
# List all feature branches
./scripts/git-state-ops.py branches \
  --governance-repo {governance_repo} \
  --feature-id {featureId} \
  --query list

# Detailed info on a specific branch
./scripts/git-state-ops.py branches \
  --governance-repo {governance_repo} \
  --feature-id {featureId} \
  --query info \
  --branch {branchName}

# Check a specific branch exists
./scripts/git-state-ops.py branches \
  --governance-repo {governance_repo} \
  --feature-id {featureId} \
  --query exists \
  --branch {branchName}
```

**list** returns all branches matching the feature's pattern with their last-commit SHA and timestamp.

**info** returns detailed metadata for a branch: last commit SHA, author, message, commit count relative to base, and last 10 log entries.

**exists** returns a simple `{ "exists": true/false }` — useful as a fast gate check.

## Branch Naming Conventions

| Pattern | Repo | Role |
| ------- | ---- | ---- |
| `{featureId}` | Governance | Base branch — approved plan merges here |
| `{featureId}-plan` | Governance | Planning artifacts accumulate here |
| `{featureId}-dev-{username}` | Governance | Per-user dev tracking (optional) |
| `feature/{featureId}-{username}` | Target repos | Actual code work (not visible from governance repo) |

Target repo branches are not visible from the governance repo; note this limitation when users ask about code branches.
