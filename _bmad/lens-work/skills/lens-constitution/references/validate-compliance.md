# Validate Compliance

Checks a feature against its resolved constitution, producing a per-check PASS/FAIL report with gate severity.

## When to Use

- At plan-commit time (before promoting to dev)
- At feature completion (before archiving)
- On demand when a developer asks "am I compliant?"

## Required Context

- Governance repo path (local checkout, constitution files on `main`)
- Feature ID
- Path to `feature.yaml` (caller extracts via `git show origin/{featureId}-plan:feature.yaml` if needed)
- Path to feature's artifacts directory (caller extracts if needed)
- Phase to check against: `planning` | `dev` | `complete`

## Caller Responsibility

The script checks local filesystem paths. If artifacts live on a `featureId-plan` branch, the caller must extract them first:

```bash
# Extract feature.yaml to a temp file
git show origin/my-feature-plan:feature.yaml > /tmp/my-feature.yaml

# Extract artifacts to a temp dir
mkdir -p /tmp/my-feature-artifacts
git show origin/my-feature-plan:planning/business-plan.md > /tmp/my-feature-artifacts/business-plan.md
```

Then pass those paths to the script.

## Output

```json
{
  "feature_id": "auth-sso",
  "domain": "platform",
  "service": "auth",
  "track": "full",
  "phase": "planning",
  "status": "PASS",
  "skipped_artifact_count": 0,
  "checks": [
    {
      "requirement": "Track 'full' permitted",
      "status": "PASS",
      "detail": "Track permitted by constitution"
    },
    {
      "requirement": "Artifact 'business-plan' present for phase 'planning'",
      "status": "PASS",
      "gate": "informational",
      "detail": "Found: /tmp/my-feature-artifacts/business-plan.md"
    },
    {
      "requirement": "Artifact 'tech-plan' present for phase 'planning'",
      "status": "FAIL",
      "gate": "informational",
      "detail": "Missing: /tmp/my-feature-artifacts/tech-plan.md"
    },
    {
      "requirement": "Reviewers configured (enforce_review=true)",
      "status": "PASS",
      "gate": "informational",
      "detail": "additional_review_participants: ['security-team']"
    }
  ],
  "hard_gate_failures": [],
  "informational_failures": ["Artifact 'tech-plan' present for phase 'planning'"]
}
```

## Script Usage

```bash
uv run scripts/constitution-ops.py check-compliance \
  --governance-repo /path/to/governance-repo \
  --feature-id auth-sso \
  --feature-yaml /tmp/auth-sso.yaml \
  --artifacts-path /tmp/auth-sso-artifacts \
  --phase planning
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | All checks pass (or only informational failures) |
| 0 | INCOMPLETE — artifacts skipped (no `--artifacts-path` provided but some required) |
| 1 | Script error (bad input, missing files, parse error) |
| 2 | Hard gate failure — workflow should block |

## Status Values

| Status | Meaning |
|--------|---------|
| `PASS` | All checks passed (or all failures are informational and gate is informational) |
| `INCOMPLETE` | Required artifact checks were skipped because `--artifacts-path` was not provided |
| `FAIL` | One or more hard-gate checks failed |

## Checks Performed

| Check | Always run | Condition |
|-------|-----------|-----------|
| Track permitted | Yes | Fails if feature's track not in `permitted_tracks` |
| Artifacts present | Only when `--artifacts-path` provided | SKIP when path not provided |
| `enforce_review` | When `enforce_review=true` in constitution | Fails if `additional_review_participants` is empty |

## Artifact Search

The script looks for each required artifact in `--artifacts-path` by checking three possible names (in order):
1. `{artifact}.md`
2. `{artifact}.yaml`
3. `{artifact}` (bare, no extension)

## Presenting Results

- **All PASS** → "Your feature satisfies all governance requirements for the `planning` phase."
- **Informational failures** → "The following are recommended but won't block your workflow: ..."
- **Hard failures** → "The following requirements must be satisfied before promotion: ..."
