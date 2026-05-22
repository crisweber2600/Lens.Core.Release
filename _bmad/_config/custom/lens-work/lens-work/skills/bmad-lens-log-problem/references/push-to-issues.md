# Push to Issues

Export unresolved problems from a feature's `problems.md` to GitHub Issues.

## Outcome

Each open problem in `problems.md` becomes a GitHub Issue in the control repo, labeled by phase and category, with a back-link to the feature. The `problems.md` entry is not modified — issues are additive and do not change the local log.

## Prerequisites

- `gh` CLI installed and authenticated
- Control repo URL known (from `feature.yaml` → `target_repos[0].url`)
- Feature's `problems.md` has at least one open problem

## Process

### Step 1 — List open problems

```bash
python3 ./scripts/log-problem-ops.py list \
  --governance-repo {governance_repo} \
  --feature-id {featureId} \
  --domain {domain} \
  --service {service} \
  --status open
```

If `total` is 0, confirm "No open problems to push." and stop.

### Step 2 — Read the control repo URL

```bash
python3 ./scripts/feature-yaml-ops.py read \
  --governance-repo {governance_repo} \
  --feature-id {featureId} \
  --field target_repos
```

Extract `url` from the first entry. If no target repo is configured, ask the user for the repo slug (`owner/repo`).

### Step 3 — Create a GitHub Issue for each open problem

For each problem in the list output:

```bash
gh issue create \
  --repo {owner/repo} \
  --title "[{featureId}] {problem.title}" \
  --body "**Feature:** {featureId}
**Phase:** {problem.phase}
**Category:** {problem.category}
**Logged:** {problem.logged}
**Entry ID:** {problem.entry_id}

## Description

{problem.description}

---
*Exported from Lens governance repo. Resolve via:*
\`\`\`
python3 ./scripts/log-problem-ops.py resolve --entry-id {problem.entry_id} ...
\`\`\`" \
  --label "lens-problem" \
  --label "phase:{problem.phase}" \
  --label "category:{problem.category}"
```

Labels `phase:{phase}` and `category:{category}` must exist in the repo or be created first. If they do not exist, create them:

```bash
gh label create "phase:{problem.phase}" --repo {owner/repo} --color "0075ca"
gh label create "category:{problem.category}" --repo {owner/repo} --color "e4e669"
```

### Step 4 — Confirm

After all issues are created, report a summary:

```
Pushed {N} issues to {owner/repo}:
  #{issue_number} — {problem.title} [{problem.phase}/{problem.category}]
  ...
```

## Notes

- This operation is idempotent in structure but not in effect — running it twice creates duplicate issues. Check for existing issues before pushing if re-running is likely.
- The `lens-problem` label acts as a sentinel for the retrospective system to query issues by feature type.
- Issues are not automatically closed when the problem is resolved in `problems.md`. Closing is a manual or retrospective workflow step.
