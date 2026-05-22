# Notify Dependents

Updates all features that reference the moved feature — replacing old path strings with the new path in every text file of every dependent feature directory.

## When to Use

After a successful `move` execution, if the `validate` output listed any `dependent_features`. Always run this step — stale references break status dashboards and planning documents.

## Identifying Dependent Features

The `validate` script identifies dependent features automatically. A feature is a dependent if it lists the moved feature's ID in any of:

- `dependencies.depends_on`
- `dependencies.blocks`
- `dependencies.related`

These are returned in the `dependent_features` array of the validate output.

## Running the Reference Patch

Use the `old_path` and `new_path` from the `move` output as patch targets:

```bash
uv run scripts/move-feature-ops.py patch-references \
  --governance-repo {governance_repo} \
  --feature-id {featureId} \
  --old-path {move_result.old_path} \
  --new-path {move_result.new_path}
```

**Output:**

```json
{
  "status": "pass",
  "files_patched": 3,
  "changes": [
    {
      "file": "features/core/billing/payment-flow/feature.yaml",
      "old": "features/platform/identity/auth-login",
      "new": "features/core/sso/auth-login"
    },
    {
      "file": "features/core/billing/payment-flow/docs/tech-plan.md",
      "old": "features/platform/identity/auth-login",
      "new": "features/core/sso/auth-login"
    }
  ]
}
```

## Dry Run First

Before patching, use `--dry-run` to preview which files will change:

```bash
uv run scripts/move-feature-ops.py patch-references \
  --governance-repo {governance_repo} \
  --feature-id {featureId} \
  --old-path {move_result.old_path} \
  --new-path {move_result.new_path} \
  --dry-run
```

The dry-run output has `"dry_run": true`. No files are modified.

## What Gets Patched

The script scans all `.md`, `.yaml`, `.yml`, `.txt`, and `.json` files under `{governance_repo}/features/` and replaces every occurrence of the old path string. This covers:

- `feature.yaml` dependency references
- Planning documents (`tech-plan.md`, `business-plan.md`, etc.)
- Sprint plans and story files
- Any cross-feature notes or summaries

## Presenting to User

After patching, show the changes:

```
✓ Reference patch complete: {files_patched} file(s) updated

  features/core/billing/payment-flow/feature.yaml
  features/core/billing/payment-flow/docs/tech-plan.md
  features/admin/dashboard/summary/summary.md
```

If `files_patched` is 0, confirm: "No reference files found containing the old path — nothing to patch."

## Manual Patch

If the script fails on a specific file, the change is simple string replacement:

- Old: `features/{old_domain}/{old_service}/{featureId}`
- New: `features/{new_domain}/{new_service}/{featureId}`

Open the file in any editor and replace all occurrences.

## Verification

After patching, search for any remaining occurrences of the old path:

```bash
grep -r "features/{old_domain}/{old_service}/{featureId}" {governance_repo}/features/
```

If any results appear, patch those files manually before committing.
