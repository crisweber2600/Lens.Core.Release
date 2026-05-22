# Cleanup

Remove legacy source locations after migration has been verified. This is a destructive operation gated by verification, explicit user confirmation, and durable proof artifacts written into the control-repo dossier.

## Outcome

Legacy branches, source repo flat legacy docs paths, feature-local `_bmad-output` artifacts, and optionally remote git branches are deleted for verified features. Cleanup writes both `cleanup-approval.yaml` and `cleanup-receipt.yaml` into the control-repo dossier so the destructive action is independently auditable.

## Safety Gate

Cleanup will **refuse to run** unless verification passes first and a `migration-record.yaml` already exists in the control-repo dossier. The script runs `verify` internally and aborts if any check fails.

Hard rules:
- **NEVER** run cleanup without verification passing
- **NEVER** run cleanup without explicit user confirmation
- **NEVER** treat chat history as the only proof of approval — the script must persist approval and receipt artifacts
- **NEVER** clean up features that were skipped or failed during migration
- Always offer `--dry-run` first to preview what will be deleted

## Process

### Dry Run (preview what will be deleted)

```bash
python3 ./scripts/migrate-ops.py cleanup \
  --governance-repo {governance_repo} \
  --old-id {old_id} \
  --feature-id {feature_id} \
  --domain {domain} \
  --service {service} \
  --source-repo {source_repo} \
  --control-repo {control_repo} \
  --dry-run
```

To also preview remote branch deletions:

```bash
python3 ./scripts/migrate-ops.py cleanup \
  --governance-repo {governance_repo} \
  --old-id {old_id} \
  --feature-id {feature_id} \
  --domain {domain} \
  --service {service} \
  --source-repo {source_repo} \
  --control-repo {control_repo} \
  --delete-remote-branches \
  --dry-run
```

### Execute Cleanup

```bash
python3 ./scripts/migrate-ops.py cleanup \
  --governance-repo {governance_repo} \
  --old-id {old_id} \
  --feature-id {feature_id} \
  --domain {domain} \
  --service {service} \
  --source-repo {source_repo} \
  --control-repo {control_repo} \
  --actor {username}
```

To also delete remote branches:

```bash
python3 ./scripts/migrate-ops.py cleanup \
  --governance-repo {governance_repo} \
  --old-id {old_id} \
  --feature-id {feature_id} \
  --domain {domain} \
  --service {service} \
  --source-repo {source_repo} \
  --control-repo {control_repo} \
  --actor {username} \
  --delete-remote-branches
```

`--source-repo` is optional. When omitted, only governance-legacy cleanup is performed.

`--control-repo` is optional. When omitted, the script tries to infer the control repo from the workspace and governance repo ancestry.

`--delete-remote-branches` is opt-in for safety. When set, legacy remote branches are discovered and deleted in both governance and source repos (base branch + milestone branches).

## Output Shape

```json
{
  "status": "pass",
  "feature_id": "auth-login",
  "dry_run": false,
  "approval_record_path": "docs/lens-work/migrations/platform/identity/auth-login/cleanup-approval.yaml",
  "cleanup_receipt_path": "docs/lens-work/migrations/platform/identity/auth-login/cleanup-receipt.yaml",
  "cleaned": [
    {
      "path": "{governance_repo}/branches/platform-identity-auth-login/",
      "type": "directory",
      "source": "governance-legacy-branch"
    },
    {
      "path": "{source_repo}/_bmad-output/lens-work/initiatives/platform/identity/auth-login-base.yaml",
      "type": "file",
      "source": "source-bmad-output-feature-file"
    }
  ],
  "branches_deleted": [
    {
      "branch": "platform-identity-auth-login",
      "repo_label": "governance",
      "command": "git -C ... push origin --delete platform-identity-auth-login"
    }
  ]
}
```

In dry-run mode, `cleaned` becomes `planned_deletions`, `branches_deleted` becomes `planned_branch_deletions`, and `dry_run` is `true`.

`branches_deleted` / `planned_branch_deletions` only appear when `--delete-remote-branches` is set and branches are found.

## Sources Cleaned

| Source | Path Pattern | When Cleaned |
|--------|-------------|--------------|
| Governance legacy branch | `{governance_repo}/branches/{old_id}/` | Always (if exists) |
| Source repo flat docs path | `{source_repo}/Docs|docs/{domain}/{service}/{legacyFeature}/` | When `--source-repo` provided and the flat legacy path exists |
| Source repo feature `_bmad-output` file | `{source_repo}/_bmad-output/lens-work/initiatives/{domain}/{service}/{legacyFeature}.yaml` | When `--source-repo` provided and file exists |
| Source repo feature `_bmad-output` dir | `{source_repo}/_bmad-output/lens-work/initiatives/{domain}/{service}/{legacyFeature}/` | When `--source-repo` provided and dir exists |
| Remote branches (governance) | `origin/{old_id}`, `origin/{old_id}-{milestone}` | When `--delete-remote-branches` set and branch exists |
| Remote branches (source) | `origin/{old_id}`, `origin/{old_id}-{milestone}` | When `--delete-remote-branches` and `--source-repo` set and branch exists |

Paths that do not exist are silently skipped.

Compatibility docs paths under `docs/{domain}/{service}/feature/{legacyFeature}/` are intentionally **not** deleted by cleanup. They remain read-compatible fallback inputs unless a later migration deliberately expands cleanup scope.

## Agent Workflow

1. Run `cleanup --dry-run` and present the deletion list plus the future approval/receipt paths to the user
2. If the feature has remote legacy branches, re-run with `--delete-remote-branches --dry-run` to include branch deletions
3. Ask for confirmation: "The following paths/branches will be permanently deleted. Proceed? (yes/no)"
4. If confirmed, run `cleanup` (live, with `--delete-remote-branches` if applicable). The script writes `cleanup-approval.yaml` before deletion and `cleanup-receipt.yaml` after deletion.
5. If declined, stop — do not re-prompt

## After Cleanup

Present a completion summary:

```
Cleanup complete:
  ✓ N sources deleted
  - N sources skipped (not found)
  ⚠ N warnings (see above)
  📄 Approval: docs/lens-work/migrations/.../cleanup-approval.yaml
  📄 Receipt: docs/lens-work/migrations/.../cleanup-receipt.yaml
```
