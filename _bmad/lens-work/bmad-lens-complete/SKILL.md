---
name: bmad-lens-complete
description: Feature lifecycle completion contract. Use when the user requests to 'complete a feature', 'finalize a feature', or 'check archive status'.
---

# Feature Completion

## Overview

This skill defines the lifecycle endpoint for Lens features. It checks whether a feature is ready to close, finalizes the archive when the user explicitly confirms, and reports whether a feature is already archived. The implementation is intentionally script-backed: prompts and agents explain the contract and run `scripts/complete-ops.py`; they never mutate governance state inline.

Act as a careful lifecycle archivist. Preserve the governance record, make irreversible actions explicit, and prefer structured JSON results over prose-only summaries.

## Operating Model

- `check-preconditions` is read-only and returns `pass`, `warn`, or `fail`.
- `finalize` is write-capable and irreversible; it must support dry-run mode and require explicit confirmation before writing.
- `archive-status` is read-only and returns the current archive state.
- Missing optional prerequisite artifacts degrade to warnings, not hard failures.
- Phase guard failures are blockers.
- All governance writes are performed by `scripts/complete-ops.py` using atomic file writes. Agents must not patch governance files directly.

## On Activation

1. Load Lens config from `{project-root}/lens.core/_bmad/lens-work/bmadconfig.yaml`.
2. If `{project-root}/.lens/governance-setup.yaml` exists and defines `governance_repo_path`, prefer it for `{governance_repo}`.
3. Resolve `{feature_id}` from the user request or active Lens context. If neither is available, ask for it.
4. Resolve `{governance_repo}`. If unavailable, stop with `config_missing`.
5. Resolve the script path: `{project-root}/lens.core/_bmad/lens-work/skills/bmad-lens-complete/scripts/complete-ops.py`.
6. If the script is absent, stop with `not_yet_implemented` and explain that this skill currently provides the command contract only; do not simulate the operation.

## Command Contract

### check-preconditions

Validates that a feature can be finalized.

Inputs:

- `--governance-repo <path>`: governance repo root.
- `--feature-id <id>`: feature identifier.
- `--dry-run`: optional; accepted for callers that always pass dry-run flags. No writes are performed either way.

Guards:

- Feature must exist in governance.
- `feature.yaml.phase` must be in a completable state: `dev`, `dev-complete`, or `complete`.
- **`retrospective.md` is a blocking prerequisite** (not advisory): the file MUST exist in the feature docs folder. If absent, return `status: fail` with `blocker: retrospective_missing` and a message directing the user to run `bmad-lens-retrospective` first. This check may not be downgraded to a warning.
- **`retrospective.md` status must be `approved`**: the file's YAML frontmatter `status` field MUST equal `approved`. If the file exists but `status` is not `approved`, return `status: fail` with `blocker: retrospective_not_approved` and the current status value.
- Missing document-project output is advisory and returns `status: warn` with `document_project_skipped: true`.
- Malformed governance YAML or an unsupported phase returns `status: fail`.

Return shape:

```json
{
  "status": "pass|warn|fail",
  "feature_id": "lens-dev-new-codebase-example",
  "phase": "dev-complete",
  "retrospective_skipped": false,
  "document_project_skipped": false,
  "checks": [
    {"name": "phase", "status": "pass", "message": "Feature is completable"},
    {"name": "retrospective", "status": "pass", "message": "retrospective.md exists and status is approved"}
  ],
  "warnings": [],
  "blockers": []
}
```

Failure shape when retrospective is missing:

```json
{
  "status": "fail",
  "blocker": "retrospective_missing",
  "message": "retrospective.md is required before completing a feature. Run 'bmad-lens-retrospective' to create it, then set status: approved."
}
```

Failure shape when retrospective exists but is not approved:

```json
{
  "status": "fail",
  "blocker": "retrospective_not_approved",
  "retrospective_status": "<current-status>",
  "message": "retrospective.md exists but status is not 'approved'. Update the file and set status: approved before completing."
}
```

Invocation:

```bash
uv run ./scripts/complete-ops.py check-preconditions \
  --governance-repo {governance_repo} \
  --feature-id {feature_id}
```

### finalize

Archives a feature after confirmation.

Inputs:

- `--governance-repo <path>`: governance repo root.
- `--feature-id <id>`: feature identifier.
- `--dry-run`: preview planned changes without writing.
- `--confirm`: required for non-dry-run execution in non-interactive contexts.

Confirmation gate:

Before non-dry-run execution, display the planned changes and require an explicit `yes` or `--confirm`. The summary must include the current phase, target phase, feature-index status change, summary path, and any skipped optional artifact warnings. If the user does not confirm, return `status: cancelled` and perform no writes.

Operations:

1. Run `check-preconditions` and require `pass` or `warn`. A `fail` status from any blocking check (including missing or unapproved retrospective) aborts finalize immediately.
2. Update `feature.yaml.phase` to `complete` and set `completed_at`.
3. Update the matching `feature-index.yaml` entry to `status: archived` and set `updated_at`.
4. Write `summary.md` if absent, or update only the generated archive section if a managed section exists.
5. Return all applied changes in structured JSON.

Dry-run return shape:

```json
{
  "status": "dry_run",
  "feature_id": "lens-dev-new-codebase-example",
  "planned_changes": [
    {"path": "features/lens-dev/new-codebase/example/feature.yaml", "change": "phase -> complete"}
  ],
  "warnings": []
}
```

Execute return shape:

```json
{
  "status": "complete",
  "feature_id": "lens-dev-new-codebase-example",
  "archived_at": "2026-04-30T00:00:00Z",
  "changes_applied": [
    {"path": "features/lens-dev/new-codebase/example/feature.yaml", "change": "phase -> complete"}
  ],
  "retrospective_skipped": false,
  "document_project_skipped": false
}
```

Invocations:

```bash
uv run ./scripts/complete-ops.py finalize \
  --governance-repo {governance_repo} \
  --feature-id {feature_id} \
  --dry-run

uv run ./scripts/complete-ops.py finalize \
  --governance-repo {governance_repo} \
  --feature-id {feature_id} \
  --confirm
```

### archive-status

Reports archive state without writing.

Inputs:

- `--governance-repo <path>`: governance repo root.
- `--feature-id <id>`: feature identifier.

Return shape:

```json
{
  "status": "pass",
  "feature_id": "lens-dev-new-codebase-example",
  "archived": true,
  "phase": "complete",
  "index_status": "archived",
  "completed_at": "2026-04-30T00:00:00Z"
}
```

Invocation:

```bash
uv run ./scripts/complete-ops.py archive-status \
  --governance-repo {governance_repo} \
  --feature-id {feature_id}
```

## Prerequisite Handling Decision

Graceful degradation is canonical. A missing retrospective or missing project-documentation artifact means the feature can still be completed when the user accepts the warning. These prerequisites are quality signals, not lifecycle state guards.

Hard blockers are limited to state and integrity failures:

- Feature not found.
- `feature.yaml` or `feature-index.yaml` cannot be parsed.
- Current phase is not completable.
- Required confirmation is absent for a non-dry-run finalize.
- Atomic write fails.

## Governance Discipline

- Always pull governance `main` before reading state.
- Never create governance branches.
- Never edit governance files with an agent patch or prompt body.
- After `finalize` writes governance state, commit and push immediately:

```bash
git -C {governance_repo} pull --rebase origin main
git -C {governance_repo} add feature-index.yaml features/
git -C {governance_repo} commit -m "[COMPLETE] {feature_id} - archive feature"
git -C {governance_repo} push origin main
```

If push fails because remote state changed, stop and surface the git error. Do not re-run `finalize` automatically.

## Error Contract

All operations return structured JSON on failure:

```json
{
  "status": "fail",
  "feature_id": "lens-dev-new-codebase-example",
  "error": "wrong_phase",
  "message": "Feature phase is preplan; expected dev, dev-complete, or complete.",
  "blockers": ["phase"]
}
```

Known error codes:

- `config_missing`
- `feature_not_found`
- `feature_yaml_malformed`
- `feature_index_malformed`
- `wrong_phase`
- `confirmation_required`
- `write_failed`
- `not_yet_implemented`

## Test Contract

The scaffolded tests in `scripts/tests/test-complete-ops.py` define the red-phase contract for the future `complete-ops.py` implementation. Each test is marked `@pytest.mark.xfail(strict=True)` and raises `NotImplementedError`, so the suite reports expected failures (xfail) now and will go red (xpass → failure) if a test starts passing before the implementation is merged.

Focused validation for the scaffold:

```bash
uv run --with pytest pytest _bmad/lens-work/skills/bmad-lens-complete/scripts/tests/test-complete-ops.py -q
```

## References

- `references/finalize-feature.md` — archive flow, confirmation gate, and governance sync expectations.
