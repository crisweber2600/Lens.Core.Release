# Dry Run

Preview the full migration plan without making any changes. This step is mandatory before execution.

## Outcome

A complete report of every action that would be taken — feature.yaml paths to be created, feature-index.yaml entries to be added, summary and problems stubs to be written, raw source documents to be mirrored into the control-repo dossier, canonical governance docs to be migrated, and any legacy state or artifacts to preserve — with no files written or modified.

## Process

For each feature in the migration plan, run with `--dry-run`:

```bash
python3 ./scripts/migrate-ops.py migrate-feature \
  --governance-repo {governance_repo} \
  --old-id {old_id} \
  --feature-id {feature_id} \
  --domain {domain} \
  --service {service} \
  --username {username} \
  --source-repo {source_repo} \
  --dry-run
```

`--source-repo` is optional. When provided, the dry run also discovers documents from legacy git branches first, then falls back to working-tree docs and feature-scoped `_bmad-output` only when the branch family produced no docs or no `_bmad-output` entries for that feature.

`--control-repo` is optional. When omitted, the script attempts to infer the control repo from the current workspace and governance repo ancestry.

## Output Shape

```json
{
  "status": "pass",
  "feature_id": "auth-login",
  "legacy_feature": "auth-login-base",
  "dry_run": true,
  "planned_actions": [
    "Create feature.yaml at {governance_repo}/features/platform/identity/auth-login/feature.yaml",
    "Update feature-index.yaml at {governance_repo}/feature-index.yaml",
    "Create summary stub at {governance_repo}/features/platform/identity/auth-login/summary.md",
    "Create problems log at {governance_repo}/features/platform/identity/auth-login/problems.md",
    "Write migration dossier at {control_repo}/docs/lens-work/migrations/platform/identity/auth-login",
    "Write migration record at {control_repo}/docs/lens-work/migrations/platform/identity/auth-login/migration-record.yaml",
    "Mirror document [branch-docs-flat:platform-identity-auth-login-dev] prd.md into the control-repo dossier",
    "Migrate canonical document [working-tree-docs-fallback:working-tree] prd.md to {governance_repo}/features/platform/identity/auth-login/docs/prd.md",
    "Migrate canonical document [governance-legacy:platform-identity-auth-login] tech-plan.md to {governance_repo}/features/platform/identity/auth-login/docs/tech-plan.md"
  ],
  "feature_yaml_created": false,
  "index_updated": false,
  "legacy_state_path": "{governance_repo}/branches/platform-identity-auth-login/initiative-state.yaml",
  "dossier_path": "{control_repo}/docs/lens-work/migrations/platform/identity/auth-login",
  "migration_record_path": "{control_repo}/docs/lens-work/migrations/platform/identity/auth-login/migration-record.yaml",
  "document_audit": {
    "control_feature_documents": 3,
    "governance_feature_documents": 2
  },
  "documents_discovered": [
    {
      "source_type": "governance-legacy",
      "source_path": "git:origin/platform-identity-auth-login:_bmad-output/lens-work/planning-artifacts/tech-plan.md",
      "relative_path": "tech-plan.md",
      "filename": "tech-plan.md",
      "git_ref": "origin/platform-identity-auth-login",
      "git_path": "_bmad-output/lens-work/planning-artifacts/tech-plan.md",
      "git_repo": "/path/to/governance",
      "commit_ts": 1700000000
    },
    {
      "source_type": "branch-docs",
      "source_path": "git:origin/platform-identity-auth-login:docs/platform/identity/auth-login-base/prd.md",
      "relative_path": "prd.md",
      "filename": "prd.md",
      "source_location": "branch-docs-flat",
      "git_ref": "origin/platform-identity-auth-login",
      "git_path": "docs/platform/identity/auth-login-base/prd.md",
      "git_repo": "/path/to/source",
      "commit_ts": 1712000000
    },
    {
      "source_type": "source-docs",
      "source_path": "/path/to/source/Docs/platform/identity/auth-login-base/prd.md",
      "relative_path": "prd.md",
      "filename": "prd.md",
      "source_location": "working-tree-docs-fallback",
      "commit_ts": 1690000000
    }
  ]
}
```

## Conflict Check

Before running the dry run for each feature, check for conflicts:

```bash
python3 ./scripts/migrate-ops.py check-conflicts \
  --governance-repo {governance_repo} \
  --feature-id {feature_id} \
  --domain {domain} \
  --service {service}
```

If `"conflict": true`, surface the conflict to the user and skip that feature in the dry-run report. Do not proceed with a conflicting feature without explicit override confirmation.

## After Dry Run

Present a summary table to the user:

| Feature ID | Old Branch | Planned Actions | Conflict |
|-----------|------------|----------------|---------|
| auth-login | platform-identity-auth-login | feature.yaml, index entry, summary, 2 docs | No |

Then ask for confirmation:
- "Proceed with migration for all N features? (yes/no)"
- OR "Select features to migrate: (all/list numbers/no)"

The preview must make the dossier location explicit so the user can see where the durable proof artifacts will be written before any destructive cleanup is ever offered. It must also surface the per-branch document audit so the user can compare branch-by-branch control counts against the governance feature-doc count before executing, including which source-location label won (`branch-docs-flat`, `branch-docs-compat`, `branch-bmad-output`, `working-tree-docs-fallback`, `working-tree-bmad-output-fallback`).

Do not proceed without explicit confirmation.
