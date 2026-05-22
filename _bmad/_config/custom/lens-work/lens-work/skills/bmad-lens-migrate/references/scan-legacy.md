# Scan Legacy Branches

Detect old-model branches in the governance repository and build a migration plan.

## Outcome

A structured migration plan listing all detected legacy features with their derived domain, service, and feature ID, proposed new branch names, discovered milestones, and inferred current state. Conflicts with existing new-model features are surfaced.

## Process

Run the scan operation:

```bash
python3 ./scripts/migrate-ops.py scan \
  --governance-repo {governance_repo}
```

With an optional custom branch pattern:

```bash
python3 ./scripts/migrate-ops.py scan \
  --governance-repo {governance_repo} \
  --branch-pattern "^your-pattern$"
```

With document discovery from a source repo:

```bash
python3 ./scripts/migrate-ops.py scan \
  --governance-repo {governance_repo} \
  --source-repo /path/to/source/repo
```

The script scans `{governance_repo}/branches/` for directories matching the legacy pattern `^([a-z0-9-]+)-([a-z0-9-]+)-([a-z0-9-]+)(?:-([a-z0-9-]+))?$`. When `branches/` does not exist on the filesystem, it falls back to listing remote branches via `git branch -r` and filtering by the same pattern. It groups only known legacy milestone suffixes under their base branch, derives domain/service/featureId, and detects conflicts. Branches that merely share a prefix with another feature remain standalone features, so names like `auth` and `auth-login` do not collapse into one migration target.

When `--source-repo` is provided, the scan also discovers documents from up to four sources per feature:
1. **governance-legacy** — `{governance_repo}/branches/{old_id}[-milestone]/_bmad-output/lens-work/planning-artifacts/` (filesystem) or `origin/{old_id}[-milestone]` branch in governance repo (git fallback)
2. **branch-docs** — `origin/{old_id}[-milestone]` branch family in source repo using the derived `legacy_feature`: `docs/{domain}/{service}/{legacyFeature}/` first, then `docs/{domain}/{service}/feature/{legacyFeature}/` as a compatibility fallback
3. **branch-bmad-output** — feature-scoped branch `_bmad-output` only: `_bmad-output/lens-work/initiatives/{domain}/{service}/{legacyFeature}.yaml` plus `_bmad-output/lens-work/initiatives/{domain}/{service}/{legacyFeature}/**`
4. **working-tree fallback** — `{source_repo}/Docs|docs/{domain}/{service}/{legacyFeature}/` and feature-scoped `_bmad-output` only when the branch family produced no docs or no `_bmad-output` entries for that feature

Scan output now also includes the inferred control-repo dossier path for each feature plus a `document_audit` block showing per-branch mirrored control-repo counts versus governance feature-doc counts.

**Prerequisite:** Ensure `git fetch` has been run on both the governance repo and source repo so remote branch refs are current.

## Output Shape

```json
{
  "status": "pass",
  "legacy_features": [
    {
      "old_id": "platform-identity-auth-login",
      "derived_domain": "platform",
      "derived_service": "identity",
      "feature_id": "auth-login",
      "milestones": ["planning", "dev"],
      "proposed": {
        "base_branch": "auth-login",
        "plan_branch": "auth-login-plan"
      },
      "state": "dev"
    }
  ],
  "total": 1,
  "conflicts": []
}
```

When `--source-repo` is provided, each feature entry also includes a `documents` array and `document_audit` summary:

```json
{
  "documents": [
    {
      "source_type": "branch-docs",
      "source_path": "git:origin/northstar-migration-feature:docs/northstar/migration/finish-northstaret-migration-3a10d3/prd.md",
      "relative_path": "prd.md",
      "filename": "prd.md",
      "source_location": "branch-docs-flat",
      "git_ref": "origin/northstar-migration-feature",
      "git_path": "docs/northstar/migration/finish-northstaret-migration-3a10d3/prd.md",
      "git_repo": "/path/to/source",
      "commit_ts": 1712000000
    },
    {
      "source_type": "bmad-output",
      "source_path": "git:origin/northstar-migration-feature:_bmad-output/lens-work/initiatives/northstar/migration/finish-northstaret-migration-3a10d3/prd.md",
      "relative_path": "prd.md",
      "filename": "prd.md",
      "source_location": "branch-bmad-output",
      "git_ref": "origin/northstar-migration-feature",
      "git_path": "_bmad-output/lens-work/initiatives/northstar/migration/finish-northstaret-migration-3a10d3/prd.md",
      "git_repo": "/path/to/source",
      "commit_ts": 1700000000
    }
  ]
}
```

```json
{
  "document_audit": {
    "control_feature_documents": 3,
    "governance_feature_documents": 2,
    "branches": [
      {
        "branch": "platform-identity-auth-login",
        "control_repo_documents": 2,
        "governance_repo_documents": 1,
        "control_repo_by_source": {
          "branch-docs-flat": 1,
          "branch-bmad-output": 1
        },
        "governance_repo_by_source": {
          "branch-docs-flat": 1
        }
      },
      {
        "branch": "platform-identity-auth-login-dev",
        "control_repo_documents": 1,
        "governance_repo_documents": 1,
        "control_repo_by_source": {
          "branch-docs-compat": 1
        },
        "governance_repo_by_source": {
          "branch-docs-compat": 1
        }
      }
    ]
  }
}
```

Git-based entries include `git_ref`, `git_path`, and `git_repo` fields. Filesystem entries do not. All entries include a `commit_ts` field (Unix epoch of the last commit that touched the file; `0` when unavailable). When the same `relative_path` appears from multiple sources, the most recently committed version is used during migration.
Working-tree fallback entries use `source_location` values `working-tree-docs-fallback` and `working-tree-bmad-output-fallback` so audits clearly show when branch-family sources were absent.

## Branch Grouping Logic

The scanner uses prefix-matching to identify milestone branches:
- If directory `A-B-C-D` exists alongside `A-B-C-D-planning`, then `planning` is a milestone of feature `A-B-C-D`
- The base branch (`A-B-C-D`) is used to derive: domain=A, service=B, featureId=C-D
- Standalone entries (not a suffix of any other) are always treated as base branches

## Conflict Detection

A conflict is detected when `{governance_repo}/features/{domain}/{service}/{featureId}/feature.yaml` already exists for the derived featureId. Conflicts are listed separately and do not block other features from appearing in the migration plan.

## After Scan

Present the migration plan as a table to the user:

| Old Branch | Feature ID | Domain | Service | Milestones | State | Conflict |
|------------|------------|--------|---------|-----------|-------|---------|
| platform-identity-auth-login | auth-login | platform | identity | planning, dev | dev | No |

Then offer to proceed to dry-run: "Ready to preview the migration? (yes/no)"
