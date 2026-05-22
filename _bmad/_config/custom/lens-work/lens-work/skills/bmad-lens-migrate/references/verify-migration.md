# Verify Migration

Validate that a migrated feature has all expected artifacts and proof records in place before cleanup. This step is mandatory — cleanup will not proceed unless verification passes.

## Outcome

A structured verification report listing each expected governance artifact, dossier artifact, and mirrored document set. Verification also refreshes `migration-record.yaml` with the latest check results.

Verification preserves the recorded `document_audit` block so reviewers can confirm which source-location labels won for each branch or fallback path.

## Process

Run verification for a single feature:

```bash
python3 ./scripts/migrate-ops.py verify \
  --governance-repo {governance_repo} \
  --feature-id {feature_id} \
  --domain {domain} \
  --service {service} \
  --control-repo {control_repo}
```

## Output Shape

```json
{
  "status": "pass",
  "feature_id": "auth-login",
  "dossier_path": "docs/lens-work/migrations/platform/identity/auth-login",
  "migration_record_path": "docs/lens-work/migrations/platform/identity/auth-login/migration-record.yaml",
  "checks": [
    { "name": "feature_yaml", "result": "pass" },
    { "name": "feature_index_entry", "result": "pass" },
    { "name": "summary_md", "result": "pass" },
    { "name": "problems_md", "result": "pass" },
    { "name": "dossier_dir", "result": "pass" },
    { "name": "migration_record", "result": "pass" },
    { "name": "mirrored_documents", "result": "pass" },
    { "name": "governance_docs", "result": "pass" }
  ],
  "document_audit": {
    "control_feature_documents": 2,
    "governance_feature_documents": 1
  }
}
```

If any check fails, `status` is `"fail"`.

## Checks Performed

| Check | Description |
|-------|-------------|
| feature_yaml | `{governance_repo}/features/{domain}/{service}/{featureId}/feature.yaml` is present |
| feature_index_entry | `{governance_repo}/feature-index.yaml` contains an entry with matching `featureId` |
| summary_md | `{governance_repo}/features/{domain}/{service}/{featureId}/summary.md` is present |
| problems_md | `{governance_repo}/features/{domain}/{service}/{featureId}/problems.md` is present |
| dossier_dir | `{control_repo}/docs/lens-work/migrations/{domain}/{service}/{featureId}/` exists |
| migration_record | `migration-record.yaml` exists in the dossier |
| mirrored_documents | Every discovered legacy document has a mirrored raw copy in the dossier `sources/` tree and its hash matches the recorded hash |
| governance_docs | Every canonical winning document exists in governance docs and its hash matches the recorded hash |

If no legacy documents were discovered, verification still requires the dossier and migration record to exist so cleanup has durable proof that the feature was checked.

When documents were discovered, the verification report should surface source-location labels such as `branch-docs-flat`, `branch-docs-compat`, `branch-bmad-output`, `working-tree-docs-fallback`, and `working-tree-bmad-output-fallback` through the persisted `document_audit` block.

## Human-in-the-Loop Workflow

After running verification, present a summary table to the user:

| Check | Status |
|-------|--------|
| feature_yaml | ✓ |
| feature_index_entry | ✓ |
| summary_md | ✓ |
| problems_md | ✓ |
| dossier_dir | ✓ |
| migration_record | ✓ |
| mirrored_documents | ✓ |
| governance_docs | ✓ |

Then:
- If all checks pass: "Verification passed. Proceed with cleanup? (yes/no)"
- If any check fails: "Verification failed — N checks did not pass. Fix the issues before cleanup."

Do not proceed to cleanup if verification fails. The user must resolve failures and re-run verification.

## Batch Verification

To verify all migrated features, run `verify` for each feature in the migration plan and aggregate results:

```
Verification summary:
  ✓ N features passed all checks
  ✗ N features have failing checks (listed below)
```

Only features that pass all checks are eligible for cleanup. Cleanup approval and receipt artifacts are written later by the cleanup command, not by verify.
